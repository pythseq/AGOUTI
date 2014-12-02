#!/usr/bin/python
"""

Script function:
Parse the output of SSPACE into scaffolding paths.
Also evaluate the accuracy of scaffolding result.

Input:
	1) xxx.final.evidence, sample line:
	
			>scaffold7|size616062|tigs4
			f_tig15680|size3634|links114|gaps98602
			f_tig15681|size279759|links13|gaps-15458
			f_tig13159|size117471|links4|gaps-22269
			f_tig11365|size116594
		
		This file contains the information of scaffolding path. In the above case,
		scaffold7 is comprised of [contig5680, contig15681,contig13159,contig11365], 
		all in forward orientation (noted the prefix"f_" denoted the orientation)
		
		However, "contig15680" is just the intermediate name assigned by SSPACE program.
		In order to figure out the original name of this contig (as provided in the
		input contig.fasta file), we also need the following file:

			
	2) 	xxx.keys,sample line:
			>contig15680|size3634|seed:scaffold.15680
		
		This file is generated by the following command:
			$ grep ">" ./intermediate_results/$prefix.sspaceout.formattedcontigs*fasta \
			> xxx.keys

Output:
	xxx.agouti.fasta
	   This file contains the scaffold scaffolds generated by SSPACE, with gaps 
	   converted to 100 'N's. Scaffolding path is also included in the ">" line.

"""

import os
import sys
import re
import string


use_message = '''
add scaffolding path information to scaffolds name in output fasta file

Usage:
    python %prog  <in.scaffolds.fasta>  <in.final.evidence>  <in.keys>  <out.fasta>
'''

def main(argv=None):
	if not argv:
		argv = sys.argv 
	if len(argv)!= 5:
		print use_message
		sys.exit()
   
	infileName_sspaceFA = argv[1]
	infileName_evid = argv[2]
	infileName_key = argv[3]
 
	outfileName_FA = argv[4]
	
	# these two output files are for evaluation only (benchmarking)
	outfileName = argv[2]+".pathout"
	outfileName_parsedEVID = argv[2]+".parsedEVID"

	
	pathnameList,pathDict = loadEVID(infileName_evid)
	print ".evidence file loaded"
	
	keyDict = loadKey(infileName_key)
	print ".key file loaded"
	
	lenList = [] #lens(contig counts) of each scaffolding paths
	parsed_pathDict = {} #key-value = pathname-orig_contigList

	# convert contig name used by sspace into original contig names
	lenList,parsed_pathDict = convertCtgName(pathnameList,pathDict,keyDict)
	print "contig names converted to original contig names"

	#compute scaffolding accuracy
	computeAccuracy(pathnameList,pathDict, keyDict,outfileName)
	print "scaffolding accuracy computed.."

	# add path info to the fasta output of sspace
	sspacenameList, sspacecontigDict = getContigsFromFile(infileName_sspaceFA)
	# check if the sspacee output contig/scaffold name is in pathnameList, if so, add path description to the name
	# add name-seq pair the ctg2spcDict

	outDict = {}
	for sspacename in sspacenameList:
		for pathname in pathnameList:
			if sspacename in pathname: #found match
				pathinfo = ",".join(parsed_pathDict[pathname])
				outseq = sspacecontigDict[sspacename]
				outDict[pathname] = {"seq":"","pathinfo":""}
				outDict[pathname]["seq"] = outseq
				outDict[pathname]["pathinfo"] = pathinfo
			else:
				continue
	outfile_FA = open(outfileName_FA,"w")
	for name in outDict:
		pathDescription = outDict[name]["pathinfo"]
		newspcSeq = outDict[name]["seq"]
		outname = name.split("|")[0]
		outfile_FA.write(">%s\t[%s]\n%s\n"%(outname,pathDescription,newspcSeq))
	outfile_FA.close()
	print "out fasta file created as: %s .."%(outfileName_FA)
	
	outfile_parsedEVID = open(outfileName_parsedEVID,"w")
	for pathname in pathnameList:
		orig_contigList =  ",".join(parsed_pathDict[pathname])
		outline = "%s\t[%s]\n"%(pathname,orig_contigList)
		outfile_parsedEVID.write(outline)
	outfile_parsedEVID.close()

def computeAccuracy(pathnameList,pathDict, keyDict, outfileName):
	"""
	this function is for evaluation only
	"""
	diffCount = 0
	sameCount = 0
	diff_nameList = [] #pathname of the paths containing non-adj. contigs
	same_nameList = [] #pathname of the paths containing adj. contigs
	lenList = [] #lens(contig counts) of each scaffolding paths
	parsed_pathDict = {} #key-value = pathname-orig_contigList

	for pathname in pathnameList:
		orig_contigList = []
		contigList = []
		for rawpath in pathDict[pathname]:
			contigID = parsePath(rawpath)
			sspace_contigName = "contig"+contigID
			orig_contigName = keyDict[sspace_contigName]
			orig_contigID = orig_contigName.split(".")[1]
			orig_contigList.append(orig_contigName)
			contigList.append(int(orig_contigID))
		parsed_pathDict[pathname] = orig_contigList

		# the following codes are only for evaluating the accuracy of sspace
		# for non-simulated data, these codes should not be used
		if len(contigList) >1 :
			if max(contigList) - min(contigList) > (len(contigList)+1)*5:
				diffCount +=1
				lenList.append(len(orig_contigList))
				diff_nameList.append(pathname)
				if pathname not in parsed_pathDict:
					parsed_pathDict[pathname] = orig_contigList
			else:
				sameCount +=1
				lenList.append(len(orig_contigList))
				same_nameList.append(pathname)
				if pathname not in parsed_pathDict:
					parsed_pathDict[pathname] = orig_contigList
	totalCount = sameCount + diffCount
	print lenList
	avgLen = float(sum(lenList))/len(lenList)
	out = "Average length of scaffolding paths is %f contigs.\n"%(avgLen)
	out0 = "Total number of scaffolding paths created by sspace is: %d\n"%(totalCount)
	out1 = "Number of rnapaths that connect contigs on same supercontigs: %d (%f)\n"%(sameCount,float(sameCount)/totalCount)
	out2 = "Number of rnapaths that connect contigs on non-adjacent supercontigs  %d\n"%(diffCount)
	outfile = open(outfileName,"w")
	outfile.write("%s\n%s\n%s\n"%(out0,out1,out2))
	count = 0
	both_nameList = same_nameList + diff_nameList
	for pathname in both_nameList:
		count +=1
		outline = ",".join(parsed_pathDict[pathname])
		outfile.write("scaffolding_path%d [%s] : %s\n"%(count,pathname,outline))
	print out
	print out0
	print out1
	print out2
	outfile.close()
	# end of codes for evaluating sspacee accuracy

def convertCtgName(pathnameList,pathDict,keyDict):
	"""
	convert contig name used by SSPACE into original contig names
	"""
	lenList = [] #lens(contig counts) of each scaffolding paths
	parsed_pathDict = {} #key-value = pathname-orig_contigList
	# convert contig name used by sspace into original contig names
	for pathname in pathnameList:
		orig_contigList = []
		contigList = []
		for rawpath in pathDict[pathname]:
			contigID = parsePath(rawpath)
			sspace_contigName = "contig"+contigID
			orig_contigName = keyDict[sspace_contigName]
			if len(orig_contigName.split('.')) == 2:
				orig_contigID = orig_contigName.split(".")[1]
			elif len(orig_contigName.split('_')) == 2:
				orig_contigID = orig_contigName.split(".")[1]
			orig_contigList.append(orig_contigName)
			contigList.append(int(orig_contigID))
		parsed_pathDict[pathname] = orig_contigList
	return lenList,parsed_pathDict

def parsePath(rawpath):
	"""
	convert 'f_tig10977|size311697|links10|gaps-10426' into '10977'
	"""
	pattern = re.compile("\d{1,}")
	contig = rawpath.split("|")[0]
	contigID = re.findall(pattern,contig)[0]
	return contigID

def loadEVID(inFileName):
	"""
	"""
	pathDict = {}
	pathnameList = []
	pathNum = 0
	tempList = []

	try:
		infile = open(inFileName)
	except IOError:
		print "Error opening infile: %s" % inFileName

	for line in infile:
		if ">" in line:
			pathname = line.strip("\n").strip(">")
			pathDict[pathname] = []
			pathnameList.append(pathname)
			pathNum += 1
			if tempList :
				prevPath = pathnameList[pathNum-2]
				pathDict[prevPath] = tempList
				tempList = []
		else:
			if line.strip("\n"):
				tempList.append(line.strip("\n"))

	pathDict[pathname] = tempList
	infile.close()
	# remove paths with only one contig
	# for key in pathnameList:
		# if len(pathDict[key]) == 1: 
			## print key,pathDict[key]
			# del pathDict[key]
	updated_pathnameList = pathDict.keys()
	return updated_pathnameList,pathDict

def loadKey(infileName_key):
	"""
	extract formatted sspace contig name and its original name
	"""
	# sample line: >contig4|size2313|read0|cov0.00|seed:scaffold_4
	keyDict = {}
	infile = open(infileName_key,"r")
	while True:
		line = infile.readline()
		if not line:
			break
		lineList = line.strip("\n").strip(">").split("|")
		sspace_contigName = lineList[0]
		orig_contigName = lineList[-1].split(":")[1]
		keyDict[sspace_contigName] = orig_contigName
		#print sspace_contigName, orig_contigName
	infile.close()
	return keyDict

def loadFASTA(contigFileName):
	nameList = []
	nameDict = {}
	contigNum = 0 
	contigDict = {}
	seq = ""

	try:
		incontigfile = open(contigFileName)
	except IOError:
		print "Error opening contig file: %s" % contigFileName
		#return contigNum, nameList, contigDict, origSize

	for line in incontigfile:
		if ">" in line:
			if len(line.split()) >1:
				chrom = line.split()[0][1:]
			else :
				chrom = line[1:-1]
				
			#print chrom #added
			nameList.append(chrom)
			nameDict[chrom] = line
			contigNum += 1
			contigDict[chrom] = ""
			if seq :
				prevChrom = nameList[contigNum-2]
				contigDict[prevChrom]=seq
				#origSize.append(len(seq))
				seq=""
		else:
			seq += line.strip()

	contigDict[chrom]=seq
	#origSize.append(len(seq))
	incontigfile.close()
	return contigNum, nameList, contigDict, nameDict

def getContigsFromFile(contigFileName):
	nameList = []
	origSize = []
	contigNum = 0 
	contigDict = {}
	seq = ""

	try:
		incontigfile = open(contigFileName)
	except IOError:
		print "Error opening contig file: %s" % contigFileName
		#return contigNum, nameList, contigDict, origSize

	for line in incontigfile:
		if ">" in line:
			if len(line.split()) >1:
				chrom = line.split()[0][1:]
			else :
				chrom = line[1:-1]
			nameList.append(chrom)
			contigNum += 1
			contigDict[chrom] = ""
			if seq :
				prevChrom = nameList[contigNum-2]
				contigDict[prevChrom]=seq
				origSize.append(len(seq))
				seq=""
		else:
			try:
				seq += line.strip()
			except MemoryError:
				print len(seq)
				print chrom

	contigDict[chrom]=seq
	origSize.append(len(seq))
	incontigfile.close()
	return  nameList, contigDict

if __name__ == "__main__":
	main()
