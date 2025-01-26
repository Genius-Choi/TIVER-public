# TIVER
TIVER is a tool for identifying adaptive versions of C/C++ open-source software (OSS) components. 

TIVER can identify duplicate components, and improve version identification accuracy by removing noise with Code Clustering Technique. Assigned adaptive Version covers various versions that coexist in reused code regions.  

Experimental results are discussed in our paper, which was published in 47th Ineternational Conference on Software Engineering (ICSE'25.)

## Running TIVER with docker
Requirements
- TIVER is avaliable with docker. The only requirement is having Docker installed on your system. 

```
docker pull geniuschoi/tiver:latest //optional
docker run -it geniuschoi/tiver:latest
```

### [1] Examples on paper
```
:/# cd tiver/tiver_public
:/tiver/tiver_public# python3 tarParser.py
:/tiver/tiver_public# python3 tiver.py
```
- Results of `ReactOS/Filament/OpenBSD(src)` as examples
- Output files will be stored under **"./output"**

### [2] Examining your own repository

#### Step1) Running CENTRIS

- TIVER operates with the output of CENTRIS as an input 
- (please refer to [this link](https://github.com/WOOSEUNGHOON/Centris-public) for CENTRIS usage details)

```
:/tiver/clonehere# git clone "YOUR_CLONE_URL" // Clone repositories you want to examine
:/tiver/clonehere# cd ../tiver_public
:/tiver/tiver_public# python3 Centris_multi.py 0 "linux"
```
- Output files of Centris will be stored under **"./res"**

#### Step2) Examining target repositories
 - **tarParser** is a preprocessor of TIVER
 - **tarParser** parses target repositories (contained in the **"../clonehere"** directory) by
hashing every function and mapping each hash value with files that contain the
corresponding function
- Running tarParser:
```
:/tiver/tiver_public# python3 tarParser.py
```
- Output files of tarParser will be stored under **"./funcs"**
#### Step3) Running TIVER
```
:/tiver/tiver_public# python3 tiver.py
```
- Output files of TIVER will be organized in the **"./output"** directory as follows:
- "./existPaths/" stands for every TLSH hash values of reused functions per OSS
component
- "./existPaths_v/" contains two forms of files.
    -  _epv: { Reused file : [versions of functions in file] } per OSS component
    -  _onevpf: { Reused file : [Prevalent version, ratio] } per OSS component. //
prevalent version is just for visualization
- "./verPerHash/" stands for the latest version of each function (as hash value) per OSS component

## Build TIVER from source code
Due to GitHub's file size limitations, we provide the full package of TIVER through Zenodo, while this repository only contains Python execution files and the paper. If you wish to build TIVER using source code instead of Docker, please refer to the files and description at [this link](https://zenodo.org/records/14541086).

## Reproducing results presented in paper
When attempting to reproduce the experimental results presented in this paper, with **[2] Examining your own repository**, please ensure to 
**clone the repository version from (or as close as possible to) April 2022.** Repositories included in docker is already a version from April 2022.

## About
This repository is authored and maintained by Youngjae Choi.

For reporting bugsm you can submit an issue to the [GitHub repository](https://github.com/Genius-Choi/TIVER-public) or send me an email(youngjaechoi@korea.ac.kr).
