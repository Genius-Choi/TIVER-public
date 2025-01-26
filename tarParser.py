import os
import sys
import tlsh
import subprocess
import re
import json

currentPath		= os.getcwd()
ctagsPath = currentPath + "/code/ctags_linux/ctags"

def computeTlsh(string):
	string 	= str.encode(string)
	hs 		= tlsh.forcehash(string)
	return hs


def removeComment(string):

	c_regex = re.compile(
		r'(?P<comment>//.*?$|[{}]+)|(?P<multilinecomment>/\*.*?\*/)|(?P<noncomment>\'(\\.|[^\\\'])*\'|"(\\.|[^\\"])*"|.[^/\'"]*)',
		re.DOTALL | re.MULTILINE)
	return ''.join([c.group('noncomment') for c in c_regex.finditer(string) if c.group('noncomment')])

def normalize(string):

	return ''.join(string.replace('\n', '').replace('\r', '').replace('\t', '').replace('{', '').replace('}', '').split(' ')).lower()

def main(inputPath, inputRepo):
	resDict, fileCnt, funcCnt, lineCnt = hashing(inputPath)
	with open('./funcs/' + inputRepo + '_funcs.txt', 'w', encoding = "UTF-8") as outfile:
		json.dump(resDict, outfile, indent=4)



def hashing(repoPath):
	possible = (".c", ".cc", ".cpp")
	fileCnt  = 0
	funcCnt  = 0
	lineCnt  = 0

	resDict  = {}
	for path, dir, files in os.walk(repoPath):
		for file in files:
			filePath = os.path.join(path, file)
			if file.endswith(possible):
				try:

					functionList 	= subprocess.check_output(ctagsPath + ' -f - --kinds-C=* --fields=neKSt "' + filePath + '"', stderr=subprocess.STDOUT, shell=True).decode()

					f = open(filePath, 'r', encoding = "UTF-8")

					lines 		= f.readlines()
					allFuncs 	= str(functionList).split('\n')
					func   		= re.compile(r'(function)')
					number 		= re.compile(r'(\d+)')
					funcSearch	= re.compile(r'{([\S\s]*)}')
					tmpString	= ""
					funcBody	= ""

					fileCnt 	+= 1

					for i in allFuncs:
						elemList	= re.sub(r'[\t\s ]{2,}', '', i)
						elemList 	= elemList.split('\t')
						funcBody 	= ""

						if i != '' and len(elemList) >= 8 and func.fullmatch(elemList[3]):
							funcStartLine 	 = int(number.search(elemList[4]).group(0))
							funcEndLine 	 = int(number.search(elemList[7]).group(0))

							tmpString	= ""
							tmpString	= tmpString.join(lines[funcStartLine - 1 : funcEndLine])

							if funcSearch.search(tmpString):
								funcBody = funcBody + funcSearch.search(tmpString).group(1)
							else:
								funcBody = " "

							funcBody = removeComment(funcBody)
							funcBody = normalize(funcBody)
							funcHash = computeTlsh(funcBody)

							if len(funcHash) == 72 and funcHash.startswith("T1"):
								funcHash = funcHash[2:]
							elif funcHash == "TNULL" or funcHash == "" or funcHash == "NULL":
								continue

							storedPath = filePath.replace(repoPath, "").replace('\\', '/')
							if funcHash not in resDict:
								resDict[funcHash] = []
							resDict[funcHash].append(storedPath)

							lineCnt += len(lines)
							funcCnt += 1

				except subprocess.CalledProcessError as e:
					print("Parser Error:", e)
					continue
				except Exception as e:
					print ("Subprocess failed", e)
					continue

	return resDict, fileCnt, funcCnt, lineCnt 

""" EXECUTE """
if __name__ == "__main__":
    directories = [d for d in os.listdir("../clonehere") if os.path.isdir(os.path.join("../clonehere", d))]
    for dir_name in directories:
        inputPath = os.path.join("../clonehere", dir_name)
        inputRepo = dir_name
        print (f"Now parsing {inputRepo}...")
        main(inputPath, inputRepo)