import os
import json
import pprint
from collections import defaultdict, Counter
import time
import re
from packaging import version
from anytree import Node, RenderTree, PreOrderIter, findall

depPath = "../dataset/deduple(1217)/"
idxPath = "../dataset/idx2ver(1217)/"

"""GLOBALS"""
zeropadding = 0
emptystring = 0
fittingversion = 0
process_percent = 0
emptystring_versions = set()
emptystring_sum = []
zeropadding_sum = []
fittingversion_sum = []
TOTALPROCESSED = 0
total_clusters_pruned = 0
total_clusters = 0
all_total_clusters = 0


class VersionNode(Node):
    def __init__(self, name, parent=None, version_info="", cluster=None, full_path="", cluster_ratio=None, oss_name=None):
        super().__init__(name, parent)
        self.version_info = version_info
        self.cluster = cluster
        self.full_path = full_path
        self.cluster_ratio = cluster_ratio
        self.oss_name = oss_name

def get_path_to_node(root, target):
    if root == target:
        return [root]
    for child in root.children:
        path = get_path_to_node(child, target)
        if path:
            return [root] + path
    return []

def process_tree(root, duplicate_file, known_dups):
    add_no_longer_combined_tag(root, duplicate_file)
    remove_unnecessary_tags(root, known_dups, duplicate_file)

def remove_unnecessary_tags(root, known_dups, duplicate_file):
    for node in root.descendants:
        if "no longer combined" in node.version_info:
            if should_remove_no_longer_combined(node, known_dups, duplicate_file):
                node.version_info = node.version_info.replace(", no longer combined", "")

def should_remove_no_longer_combined(node, known_dups, duplicate_file):
    if "no longer combined" not in node.version_info:
        return False
    
    leaf_nodes = [leaf for leaf in node.leaves]
    unknown_duplicate_count = 0
    
    for leaf in leaf_nodes:
        file_name = (os.path.basename(leaf.full_path)).split('.')[0]
        if file_name not in duplicate_file:
            continue
        
        actual_count = len(duplicate_file[file_name])
        
        if file_name not in known_dups.get(node.oss_name, {}):
            unknown_duplicate_count += 1
            if unknown_duplicate_count > 1:
                return False
            continue
        
        known_count = known_dups[node.oss_name][file_name]
        
        if actual_count > known_count:
            return False
    
    return True

def find_node_by_path(root, path):
    current = root
    parts = path.split('/')
    for part in parts[1:]:
        for child in current.children:
            if child.name == part:
                current = child
                break
        else:
            return None
    return current

def add_no_longer_combined_tag(root, duplicate_file):
    for duplicate_set in duplicate_file.values():
        if len(duplicate_set) < 2:
            continue
        
        nodes = [find_node_by_path(root, path) for path in duplicate_set]
        nodes = [node for node in nodes if node]
        
        if len(nodes) < 2:
            continue

        for i in range(len(nodes)):
            for j in range(i + 1, len(nodes)):
                lca = find_lca(root, nodes[i], nodes[j])
                if lca and lca != root and "no longer combined" not in lca.version_info:
                    lca.version_info += ", no longer combined"

def find_lca(root, node1, node2):
    if root is None or root == node1 or root == node2:
        return root
    
    path1 = get_path_to_node(root, node1)
    path2 = get_path_to_node(root, node2)

    common_path = []
    for n1, n2 in zip(path1, path2):
        if n1 == n2:
            common_path.append(n1)
        else:
            break
    
    return common_path[-1] if common_path else root

def get_all_unique_versions(existPaths_v):
    all_versions = set()
    for versions in existPaths_v.values():
        all_versions.update(versions)
    return sorted(all_versions, key=lambda v: version.parse(v) if v else version.parse("0"))

def adaptive_versioning_pruned(root, should_print_cluster, existPaths_v, OSSname):
    pruned_paths = set()
    
    for node in PreOrderIter(root):
        if node.cluster:
            cluster_nodes = [n for n in PreOrderIter(node) if n.cluster == node.cluster]
            if should_print_cluster(node.cluster, cluster_nodes):
                for leaf in [n for n in cluster_nodes if n.is_leaf]:
                    pruned_paths.add(leaf.full_path)

    pruned_versions = {path: versions for path, versions in existPaths_v.items() if path in pruned_paths}
    combined_adaptive_version = adaptive_versioning(pruned_versions)

    for node in PreOrderIter(root):
        if node.cluster:
            cluster_nodes = [n for n in PreOrderIter(node) if n.cluster == node.cluster]
            if should_print_cluster(node.cluster, cluster_nodes):
                cluster_root = find_cluster_root(cluster_nodes)
                if cluster_root:
                    cluster_versions = {n.full_path: existPaths_v[n.full_path] for n in cluster_nodes if n.is_leaf and n.full_path in existPaths_v}
                    adaptive_version = adaptive_versioning(cluster_versions)
                    if adaptive_version:
                        cluster_root.adaptive_version = adaptive_version

    return combined_adaptive_version

def print_cluster_trees_with_adaptive_version(root, output_file, epv, combined_adaptive_version):
    global total_clusters_pruned, total_clusters, all_total_clusters

    cluster_trees = defaultdict(list)
    for node in PreOrderIter(root):
        if node.cluster and "no longer combined" not in node.version_info:
            cluster_trees[node.cluster].append(node)

    total_clusters = len(cluster_trees)
    all_total_clusters += total_clusters
    pruned_clusters = 0
    
    output_file.write(f"After pruning: [{combined_adaptive_version}]")

    for cluster, nodes in cluster_trees.items():
        cluster_root = find_cluster_root(nodes)
        if cluster_root and cluster_root.cluster_ratio:
            if float(cluster_root.cluster_ratio) > 0.03:
                cluster_versions = {}
                for node in PreOrderIter(cluster_root):
                    if node.is_leaf and node.full_path in epv:
                        cluster_versions[node.full_path] = epv[node.full_path]
                        
                adaptive_version = adaptive_versioning(cluster_versions)
                cluster_root.adaptive_version = adaptive_version

                output_file.write(f"\nCluster {cluster}'s adaptive version: {adaptive_version}\n\n")
                for pre, _, node in RenderTree(cluster_root):
                    if node.cluster == cluster:
                        version_info = f" [{node.version_info}]" if node.version_info else ""
                        output_file.write(f"{pre}{node.name}{version_info}\n")
            else:
                pruned_clusters += 1

    total_clusters_pruned += pruned_clusters
    output_file.write(f"\nPruned {pruned_clusters} clusters.\n")

def find_cluster_root(nodes):
    for node in nodes:
        if node.parent is None or node.parent.cluster != node.cluster:
            return node
    return nodes[0] if nodes else None

def should_print_cluster(cluster, nodes):
    root_node = find_cluster_root(nodes)
    if root_node and root_node.cluster_ratio:
        return float(root_node.cluster_ratio) > 0.03
    return False

def create_dupledict(onevpf):
    file_map = defaultdict(list)
    
    for path in onevpf.keys():
        filename = os.path.splitext(os.path.basename(path))[0]
        file_map[filename].append(path)
    
    duplicates = {filename: paths for filename, paths in file_map.items() if len(paths) > 1}
    
    return duplicates

def load_known_duplicates(OSSname):
    try:
        with open(f'./knownDuplicates/{OSSname}.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def get_prevalent_version(versions):
    counter = Counter(versions)
    most_common_versions = counter.most_common()
    max_count = most_common_versions[0][1]
    prevalent_versions = [version.parse(ver) for ver, count in most_common_versions if count == max_count]
    if len(prevalent_versions) > 1:
        prevalent_version = max(prevalent_versions)
    else:
        prevalent_version = prevalent_versions[0]

    prevalent_version_str = str(prevalent_version)
    
    return f"{prevalent_version_str}, {max_count}/{len(versions)}"

def build_tree(existPaths_v, OSSname):
    root = VersionNode("", version_info="", full_path="/", oss_name=OSSname)
    nodes = {"": root}

    for path, versions in existPaths_v.items():
        parts = path.lstrip('/').split('/')
        for i in range(len(parts)):
            current_path = '/'.join(parts[:i+1])
            parent_path = '/'.join(parts[:i])
            if current_path not in nodes:
                version_info = get_prevalent_version(versions) if i == len(parts) - 1 else ""
                full_path = '/' + current_path
                nodes[current_path] = VersionNode(parts[i], parent=nodes.get(parent_path, root), 
                                                  version_info=version_info, full_path=full_path, oss_name=OSSname)

    for node in reversed(list(root.descendants)):
        if not node.version_info:
            child_versions = [child.version_info.split(',')[0].strip() for child in node.children if child.version_info]
            if child_versions:
                node.version_info = get_prevalent_version(child_versions)

    return root

def assign_clusters(root, duplicate_file):
    global_cluster_counter = 0

    def find_duplicate_descendants(node, duplicate_file):
        duplicate_nodes = {}
        for leaf in node.leaves:
            file_name = os.path.splitext(leaf.name)[0]
            if file_name in duplicate_file:
                if file_name not in duplicate_nodes:
                    duplicate_nodes[file_name] = []
                duplicate_nodes[file_name].append(leaf)
        return duplicate_nodes

    def assign_cluster_recursive(node, parent_cluster):
        nonlocal global_cluster_counter

        if "no longer combined" in node.version_info:
            node.cluster = None
            duplicate_descendants = find_duplicate_descendants(node, duplicate_file)
            
            for child in node.children:
                child_duplicates = [
                    leaves for file_name, leaves in duplicate_descendants.items()
                    if any(leaf in child.leaves for leaf in leaves)
                ]
                
                if any(len(leaves) > 1 for leaves in child_duplicates):
                    global_cluster_counter += 1
                    child_cluster = f"C{global_cluster_counter}"
                    assign_cluster_recursive(child, child_cluster)
                else:
                    assign_cluster_recursive(child, parent_cluster)
        else:
            node.cluster = parent_cluster
            for child in node.children:
                assign_cluster_recursive(child, parent_cluster)

    root.cluster = None

    for child in root.children:
        global_cluster_counter += 1
        child_cluster = f"C{global_cluster_counter}"
        assign_cluster_recursive(child, child_cluster)

def calculate_cluster_ratios(root, existPaths_v):
    total_denominator = sum(len(versions) for versions in existPaths_v.values())
    cluster_denominators = {}

    for node in root.descendants:
        if node.is_leaf and node.cluster:
            cluster_denominators[node.cluster] = cluster_denominators.get(node.cluster, 0) + int(node.version_info.split('/')[1])

    cluster_top_nodes = {}
    for node in root.descendants:
        if node.cluster and (node.cluster not in cluster_top_nodes or node.depth < cluster_top_nodes[node.cluster].depth):
            cluster_top_nodes[node.cluster] = node

    for cluster, node in cluster_top_nodes.items():
        ratio = cluster_denominators.get(cluster, 0) / total_denominator
        node.cluster_ratio = f"{ratio:.3f}"

def adaptive_versioning(epv):
    allver_withoutblank = [
        v 
        for versions in epv.values()
        for v in versions
        if v
        ]
    
    allver_withblank = [
        v 
        for versions in epv.values()
        for v in versions
        ]
    
    if not allver_withoutblank:
        return None
    
    oldestVersion = min(allver_withoutblank, key=version.parse)
    oldestVerObj = version.parse(oldestVersion)
    
    if len(set(allver_withblank)) == 2 and '' in set(allver_withblank):
        representative_version = f"+{oldestVersion}"
        return representative_version
    
    majorDiff = any(version.parse(v).release[0] != oldestVerObj.release[0] for v in allver_withoutblank)
    minorDiff = any(
        len(version.parse(v).release) > 1 and version.parse(v).release[1] != oldestVerObj.release[1]
        for v in allver_withoutblank
    )
    patchDiff = any(
        len(version.parse(v).release) > 2 and version.parse(v).release[2] != oldestVerObj.release[2]
        for v in allver_withoutblank
    )
    
    if majorDiff:
        representative_version = f"*{oldestVersion}"
    elif minorDiff:
        representative_version = f"^{oldestVersion}"
    elif patchDiff:
        representative_version = f"~{oldestVersion}"
    elif len(set(allver_withoutblank)) == 1:
        representative_version = oldestVersion
    else:
        representative_version = 'VERSION ERROR'
    
    return representative_version

def calculate_oss_adaptive_version(versions):
    allver_withoutblank = [v for v in versions if v]
    allver_withblank = versions
    
    if not allver_withoutblank:
        return None
    
    oldestVersion = min(allver_withoutblank, key=version.parse)
    oldestVerObj = version.parse(oldestVersion)
    
    if len(set(allver_withblank)) == 2 and '' in set(allver_withblank):
        representative_version = f"+{oldestVersion}"
        return representative_version
    
    majorDiff = any(version.parse(v).release[0] != oldestVerObj.release[0] for v in allver_withoutblank)
    minorDiff = any(
        len(version.parse(v).release) > 1 and version.parse(v).release[1] != oldestVerObj.release[1]
        for v in allver_withoutblank
    )
    patchDiff = any(
        len(version.parse(v).release) > 2 and version.parse(v).release[2] != oldestVerObj.release[2]
        for v in allver_withoutblank
    )
    
    if majorDiff:
        representative_version = f"*{oldestVersion}"
    elif minorDiff:
        representative_version = f"^{oldestVersion}"
    elif patchDiff:
        representative_version = f"~{oldestVersion}"
    elif len(set(allver_withoutblank)) == 1:
        representative_version = oldestVersion
    else:
        representative_version = 'VERSION ERROR'
    
    return representative_version

def normalize_version_nc(version):
    version_numbers = re.findall(r'\d+', version)

    if len(version_numbers) <= 1:
        return ''
    
    major = version_numbers[0]
    delimiter = None
    minor = ''
    patch = ''

    for char in version[len(major):]:
        if not char.isdigit() and not char.isalpha():
            delimiter = char
            break

    if delimiter:
        parts = version.split(delimiter)
        parts = [part for part in parts if re.search(r'\d+', part)]
        if len(parts) > 1 and re.search(r'\d+', parts[1]):
            minor = re.search(r'\d+', parts[1]).group()
        
        if len(parts) > 2 and re.search(r'\d+', parts[2]):
            patch = re.search(r'\d+', parts[2]).group()

    if major and minor and not patch:
        patch = '0'
    
    if not major or not minor:
        return ''
    
    return f"{major}.{minor}.{patch}"

def normalize_version(version):
    global emptystring, zeropadding, fittingversion, emptystring_versions
    version_numbers = re.findall(r'\d+', version)
    
    if len(version_numbers) <= 1:
        emptystring += 1
        if version not in emptystring_versions:
            emptystring_versions.add(version)
        return ''
    
    major = version_numbers[0]
    delimiter = None
    minor = ''
    patch = ''
    starthere = version.find(major)
    
    for char in version[starthere:]:
        if not char.isdigit() and not char.isalpha():
            delimiter = char
            break

    if delimiter:
        parts = version.split(delimiter)
        parts = [part for part in parts if re.search(r'\d+', part)]
        if len(parts) > 1 and re.search(r'\d+', parts[1]):
            minor = re.search(r'\d+', parts[1]).group()
        
        if len(parts) > 2 and re.search(r'\d+', parts[2]):
            patch = re.search(r'\d+', parts[2]).group()

    if major and minor and not patch:
        zeropadding += 1
        patch = '0'
        return f"{major}.{minor}.{patch}"
    
    if not major or not minor:
        emptystring += 1
        return ''
    
    fittingversion += 1
    return f"{major}.{minor}.{patch}"


def main(input, inputfunc):
    global emptystring, TOTALPROCESSED
    global zeropadding
    global fittingversion
    
    tar_oss_name = input.split('/')[-1].split('_')[0]
    output_path =  "./output/" + tar_oss_name + "_output.txt"
    ep_path =  "./existPaths/" + tar_oss_name + "_ep.txt"
    epv_path =  "./existPaths_v/" + tar_oss_name + "_epv.txt"
    vph_path = "./verPerHash/" + tar_oss_name + "_vph.txt"


    with open(inputfunc, 'r', encoding = "UTF-8") as ff:
        tarfuncs = json.load(ff)

    with open(input, 'r', encoding = "UTF-8") as fp:
        body = fp.readlines()
        with open(output_path, 'w', encoding="UTF-8") as output_path, \
            open(ep_path, 'w', encoding='UTF-8') as ep_path, \
            open(epv_path, 'w', encoding='UTF-8') as epv_path, \
            open(vph_path, 'w', encoding='UTF-8') as vph_path, \
            open("./existPaths_v/" + tar_oss_name + "_onevpf.txt", 'w', encoding='UTF-8') as onevpf:
            
            for eachOSS in body:
                emptystring = 0
                zeropadding = 0
                fittingversion = 0
                allFuncs = {}
                allPaths = {}
                existPaths = {}
                existPaths_v = {}
                verperHash = {}
                
                if eachOSS.startswith("OSS: "):
                    OSSname		= eachOSS.strip().split('OSS: ')[1].split('_sig')[0]
                    OSSVerDict 	= {}
                    OSSDepDict 	= {}
                    OSSidxFile 	= OSSname + "_idx.txt"
                    OSSdepFile 	= OSSname + "_deduple.txt"

                    if not os.path.isfile(idxPath + OSSidxFile) or not os.path.isfile(depPath + OSSdepFile):
                        continue

                    with open(idxPath + OSSidxFile, 'r', encoding = "UTF-8") as fi:
                        OSSVerDict = json.load(fi)
                    for eachVer in OSSVerDict:
                        allFuncs[str(eachVer)] = 0

                    with open(depPath + OSSdepFile, 'r', encoding = "UTF-8") as fd:
                        OSSDepDict = json.load(fd)

                    for OSSfunc in OSSDepDict:
                        if OSSfunc in tarfuncs:
                            if OSSfunc not in verperHash:
                                verperHash[OSSfunc] = []
                            if len(OSSDepDict[OSSfunc]) > 1:
                                verperHash[OSSfunc].append(normalize_version_nc(OSSVerDict[str(OSSDepDict[OSSfunc][-1])]))
                            else:
                                verperHash[OSSfunc].append(normalize_version_nc(OSSVerDict[str(OSSDepDict[OSSfunc][0])]))
                            
                            for eachPath in tarfuncs[OSSfunc]:
                                if eachPath not in allPaths:
                                    allPaths[eachPath] = 0
                                    existPaths[eachPath] = []
                                    existPaths_v[eachPath] = []
                                allPaths[eachPath] += 1
                                existPaths[eachPath].append(OSSfunc)
                                
                                if len(OSSDepDict[OSSfunc]) > 1:
                                    existPaths_v[eachPath].append(normalize_version(OSSVerDict[str(OSSDepDict[OSSfunc][-1])]))
                                else:
                                    existPaths_v[eachPath].append(normalize_version(OSSVerDict[str(OSSDepDict[OSSfunc][0])]))
                            
                            if len(OSSDepDict[OSSfunc]) > 1:
                                allFuncs[str(OSSDepDict[OSSfunc][-1])] += 1
                            else:
                                allFuncs[str(OSSDepDict[OSSfunc][0])] += 1
                                
                                
                    if OSSname.split('@@')[-1] != tar_oss_name:
                        ep_path.write(f"\n{OSSname}\n")
                        epv_path.write(f"\n{OSSname}\n")
                        vph_path.write(f"\n{OSSname}\n")
                        
                        ep_path.write(json.dumps(existPaths))
                        epv_path.write(json.dumps(existPaths_v))
                        vph_path.write(json.dumps(verperHash))

                        oneVerPerFile = {}

                        for P,V in existPaths_v.items():
                            tmp = []
                            if len(set(V)) == 1:
                                tmp.append(V[0])
                                tmp.append(f'{len(V)}/{len(V)}')
                                oneVerPerFile[P] = tmp
                                TOTALPROCESSED += len(V)
                            else:
                                counter = Counter(V)
                                mc = counter.most_common()
                                max_count = mc[0][1]
                                most_common_versions = [v for v, c in mc if c == max_count]
                                highest_version = max(most_common_versions, key=lambda x: version.parse(x))
                                tmp.append(highest_version)
                                tmp.append(f'{counter[highest_version]}/{len(V)}')
                                oneVerPerFile[P] = tmp
                                TOTALPROCESSED += len(V)

                        onevpf.write(f"\n{OSSname}\n")
                        onevpf.write(json.dumps(oneVerPerFile))
                        
                        duplicate_file = create_dupledict(oneVerPerFile)
                        known_dups = load_known_duplicates(OSSname)

                        output_path.write('-------------------------------------------------------------------\n')
                        output_path.write(f"\n{OSSname}\n")
                        output_path.write("\nKnown:\n")
                        pprint.pprint(known_dups, stream=output_path)
                        output_path.write("\nActual:\n")
                        pprint.pprint(duplicate_file, stream=output_path)

                        tree = build_tree(existPaths_v, OSSname)
                        process_tree(tree, duplicate_file, known_dups)
                        assign_clusters(tree, duplicate_file)
                        calculate_cluster_ratios(tree, existPaths_v)
                        
                        all_versions = get_all_unique_versions(existPaths_v)
                        output_path.write("\nEvery version used in this OSS: ")
                        output_path.write(", ".join(all_versions) + "\n")
                        oss_adaptive_version = calculate_oss_adaptive_version(all_versions)
                        output_path.write(f"Full Tree Structure:\n")
                        output_path.write(f"Root[{oss_adaptive_version}]") 
                        
                        for pre, _, node in RenderTree(tree):
                            cluster_info = f", {node.cluster}" if node.cluster else ""
                            ratio_info = f", {node.cluster_ratio}" if node.cluster_ratio else ""
                            version_info = f" [{node.version_info}{cluster_info}{ratio_info}]" if node.version_info else ""
                            output_path.write(f"{pre}{node.name}{version_info}\n")
                        
                        output_path.write('\n\n')
                        
                        combined_adaptive_version = adaptive_versioning_pruned(tree, should_print_cluster, existPaths_v, OSSname)
                        print_cluster_trees_with_adaptive_version(tree, output_path, existPaths_v, combined_adaptive_version)

                    else:
                        continue

                    emptystring_sum.append(emptystring)
                    zeropadding_sum.append(zeropadding)
                    fittingversion_sum.append(fittingversion)


if __name__ == "__main__":
    #---------------------------------------↓↓↓Use here for general↓↓↓---------------------------------------#
    res_files = [f for f in os.listdir("./res") if os.path.isfile(os.path.join("./res", f))]
    for resfile in res_files:
        try:
            inputfile = "./res/" + resfile
            inputfunc = "./funcs/" + resfile.rsplit('_', 1)[0] + "_" + "funcs.txt"
            tar_oss_name = inputfile.split('/')[-1].split('_res.txt')[0]
            process_percent += 1
            print(f"Now Processing {tar_oss_name}... {process_percent}/{len([f for f in os.listdir('./res') if os.path.isfile(os.path.join('./res', f))])}")
            main(inputfile, inputfunc)

        except FileNotFoundError as e:
            continue

    outputFiles = [f for f in os.listdir("./output") if os.path.isfile(os.path.join("./output", f))]
    
    toDel = 0
    for file in outputFiles:
        file_path = os.path.join("output", file)
        if os.path.getsize(file_path) == 0:
            print(f"Deleted empty file: {file}")
            toDel += 1
            os.remove(file_path)
    #---------------------------------------↑↑↑Use here for general↑↑↑---------------------------------------#



    #---------------------------------------↓↓↓Use here for testing↓↓↓---------------------------------------#
    # inputfile = "./res/filament_res.txt"
    # inputfunc = "./funcs/filament_funcs.txt"
    # inputfile = "./res/reactos_res.txt"
    # inputfunc = "./funcs/reactos_funcs.txt"
    # inputfile = "./res/src_res.txt"
    # inputfunc = "./funcs/src_funcs.txt"
    # main(inputfile, inputfunc)
    #---------------------------------------↑↑↑Use here for testing↑↑↑---------------------------------------#



    print(f'\nEmpty string: {sum(emptystring_sum)}/{TOTALPROCESSED}')
    print(f'Zero padding: {sum(zeropadding_sum)}/{TOTALPROCESSED}')
    print(f'Fitting version: {sum(fittingversion_sum)}/{TOTALPROCESSED}')
    print(f"{total_clusters_pruned}/{all_total_clusters} clusters pruned.")