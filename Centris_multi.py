import os
import sys
import re
import shutil
import json
import tlsh
import subprocess

"""GLOBALS"""
currentPath		= os.getcwd()
theta			= 0.1
resultPath		= currentPath + "/res/"
finalDBPath		= currentPath + "/code/componentDB/"
aveFuncPath		= currentPath + "/code/configFiles/aveFuncs"
ctagsPath		= ""

shouldMake 	= [resultPath]
for eachRepo in shouldMake:
	if not os.path.isdir(eachRepo):
		os.mkdir(eachRepo)

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

							storedPath = filePath.replace(repoPath, "")

							resDict[funcHash] = storedPath


							lineCnt += len(lines)
							funcCnt += 1

				except subprocess.CalledProcessError as e:
					continue
				except Exception as e:
					continue

	return resDict, fileCnt, funcCnt, lineCnt 

def getAveFuncs():
	aveFuncs = {}
	with open(aveFuncPath, 'r', encoding = "UTF-8") as fp:
		aveFuncs = json.load(fp)
	return aveFuncs

def readComponentDB():
	componentDB = {}
	jsonLst 	= []

	for OSS in os.listdir(finalDBPath):
		componentDB[OSS] = []
		with open(finalDBPath + OSS, 'r', encoding = "UTF-8") as fp:
			jsonLst = json.load(fp)
			for eachHash in jsonLst:
				hashval = eachHash["hash"]
				componentDB[OSS].append(hashval)
	return componentDB

def detector(inputDict, inputRepo):
    with open(resultPath + inputRepo + "_res.txt", 'w', encoding='UTF-8') as fres:
     aveFuncs 	= getAveFuncs()
     cnt = 0
     for OSS in os.listdir(finalDBPath):
            OSSHashes = []
            commonFunc 	= []
            repoName 	= OSS.split('_sig')[0]
            totOSSFuncs = float(aveFuncs[repoName])
            if totOSSFuncs == 0.0:
                continue
            with open(finalDBPath + OSS, 'r', encoding = "UTF-8") as fp:
                jsonLst = json.load(fp)
                for eachHash in jsonLst:
                    hashval = eachHash["hash"]
                    OSSHashes.append(hashval)

            comOSSFuncs = 0.0
            for hashval in OSSHashes:
                if hashval in inputDict:
                    commonFunc.append(hashval)
                    comOSSFuncs += 1.0		

            if (comOSSFuncs/totOSSFuncs) >= theta:
                fres.write("OSS: " + OSS + '\n')
                
                for hashFunction in commonFunc:
                    fres.write('\t' + inputDict[hashFunction] + '\n')




def main(inputPath, inputRepo, testmode, osmode):
	global ctagsPath
    
	if osmode == "win":
		ctagsPath = currentPath + "/code/ctags_windows/ctags.exe"
	elif osmode == "linux":
		ctagsPath = currentPath + "/code/ctags_linux/ctags"
	else:
		print ("Please enter the correct OS mode! (win|linux)")
		sys.exit()

	if testmode == "1":
		inputDict = {}
		with open(inputPath, 'r', encoding = "UTF-8") as fp:
			body = ''.join(fp.readlines()).strip()
			for eachLine in body.split('\n')[1:]:
				hashVal = eachLine.split('\t')[0]
				hashPat = eachLine.split('\t')[1]
				inputDict[hashVal] = hashPat
	else:
		inputDict, fileCnt, funcCnt, lineCnt = hashing(inputPath)
	
	print (f"Centris-ing {inputPath.split('/')[-1]}...")
	detector(inputDict, inputRepo)



def Centris_Multi(testmode, osmode):
    testhere_path = "../clonehere"
    directories = [d for d in os.listdir(testhere_path) if os.path.isdir(os.path.join(testhere_path, d))]

    for directory in directories:
        inputPath = os.path.join(testhere_path, directory)
        inputRepo = directory
        main(inputPath, inputRepo, testmode, osmode)


""" EXECUTE """
if __name__ == "__main__":
        
    testmode  = sys.argv[1]
    osmode    = sys.argv[2]

    Centris_Multi(testmode, osmode)
