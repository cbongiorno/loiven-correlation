#!/usr/bin/python

import sys, getopt
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from collections import Counter,defaultdict
import scipy.stats as st
from matplotlib.pylab import flatten
from multiprocessing import Pool
import random as rd
from copy import deepcopy

def floatingPointError(H):
	H[np.logical_and(H<1e-12,H>-1e-12)]=0
	return H


def RMT_av(X,q,method='Pos',rem_mode=False):
	'''
	'Input Correlation Matrix, Dimension of TimeSeries (N,M),method'+
	' "PosNeg" take out l{max} and l-<l<+l; "PosNeg_wMod" take out just l-<l<+l;'
	'''
	N,M = q
	
	LM = (1+np.sqrt(N/float(M)))**2
	#Lm = (1-np.sqrt(N/float(M)))**2
	

	if rem_mode==True:
		R = np.corrcoef( X - X.mean(axis=0) )
	else:
		R = np.corrcoef( X )
	
	l,v = np.linalg.eig(R)
	
	l,v = map( np.array,zip(* sorted(zip(l,v.T),reverse=True) ) )
	v = v.T
	
	
	Cr = np.zeros((len(l),len(l)))

	for i in range(len(l)):
		if l[i]<LM:
			S = np.outer(v[i],v[i])*l[i]
			Cr+= S.real
			
	l = np.array(l)	
	if method=='Pos':
		xv = (sum(l[l>=LM]))/float(N)
		return floatingPointError(R -Cr),xv
	elif method=='All':
		return R,1.0
	else:
		print("BUG")
		return None

def Cntr1(R):
	rr = R.copy()
	np.fill_diagonal(rr,0)
	np.fill_diagonal(rr,rr.max(axis=0))
	
	s = rr.sum(axis=0)/np.sqrt(rr.sum())
	
	return R - np.outer(s,s)

def RMT(A,q,method='Pos',rem_mode=False):
	'''
	'Input Correlation Matrix, Dimension of TimeSeries (N,M),method'+
	' "PosNeg" take out l{max} and l-<l<+l; "PosNeg_wMod" take out just l-<l<+l;'
	'''
	N,M = q
	
	if method=='Cntr' and rem_mode==False:
		return A,0
	elif method=='Cntr' and rem_mode==True:
		return Cntr1(A),0

	LM = (1+np.sqrt(N/float(M)))**2
	Lm = (1-np.sqrt(N/float(M)))**2
	
	l,v = np.linalg.eig(A)
	
	v = [v[:,i] for i in range(len(v))]
	
	l,v = zip(*sorted(zip(l,v),reverse=True,key=lambda x:x[0]))

	

	Cm =(np.outer(v[0],v[0])*l[0]).real
	Cr = np.zeros((len(l),len(l)))

	for i in range(len(l)):
		if l[i]<LM:
			S = np.outer(v[i],v[i])*l[i]
			Cr+= S.real
			
	l = np.array(l)	
	if method=='Pos' and rem_mode==True:
		xv = (sum(l[l>=LM])-max(l))/float(N)
		return floatingPointError(A-Cr-Cm),xv
	elif method=='Pos' and rem_mode==False:
		xv = (sum(l[l>=LM]))/float(N)
		return floatingPointError(A -Cr),xv
	elif method=='All' and rem_mode==False:
		return A,1.0
	elif method=='All' and rem_mode==True:
		return floatingPointError(A-Cm),1.0 - l[0]/float(N)
	else:
		print("BUG")
		return None





def UpdateSigma(sigma,R):
    return np.array([[p for x in c for p in sigma[x]] for c in R ])

def to_Membership(sigma,N):
    M = np.zeros(N)
    for i,r in enumerate(sigma):
        M[r] = i
    return M
    

def Modulize(B,sgl):
	Q = np.diagonal(B).sum()	#Initial Modularity
	N = len(B)
	M = dict(zip(range(N),range(N)))	#The Membership
	
	'Create Membership Matrix'
	C = np.zeros((N,N))
	np.fill_diagonal(C,True)
	
	'Shuffle the priority list of nodes'
	Nx = list(range(N))
	rd.shuffle(Nx)

	count=0
	k=0
	xcount = 0
	Q0 = Q
	'Do it until no futher improvement are possile'
	while True:
		
		xcount+=1
		if xcount%N==0: 
			if Q>Q0: Q0 = Q	#if it is an improvement change Q -> Q0
			else: break 	#if no improvment exit
		
		
		i = Nx[k]	#The node
		ci = M[i]	#Th membership of the node
		
		'For any neighbors of node-i evaluate the increment of modularity'
		dQ = []
		for j in range(N):
			cj = M[j]		#The membership of the j-node 
			if ci==cj: continue
			
			dQ.append((2*B[i,np.where(C[cj])].sum() - 2*B[i,np.where(C[ci])].sum() + 2*B[i,i],j))	#The increment of modularity
			
		if len(dQ)==0: continue	#No possible movement
		dQ,j = max(dQ)	#Select the movement with the maximum modularity
		cj = M[j]		#the destiantion membership
		'If does not provide a sigificant improvement skip it'
		if dQ>sgl:
			count=0
			C[cj,i] = True
			C[ci,i] = False
			M[i] = cj
			Q+=dQ
		else:
			count+=1
		'If no improvement break (why it is also up?)'
		if count>=N:
			break
		k+=1
		if k>=N: k=0
			 
	return C,Q

def get_comm(C):
    R = defaultdict(list)
    for a,b in zip(*np.where(C)):
        R[a].append(b)
    R = np.array([np.array(R[k]) for k in R])
    return R

def renormlize(B,R):
    return np.array([[sum(B[l,m] for l in R[i] for m in R[j]) for i in range(len(R))] for j in range(len(R))])

def LouvainMod_Hier(q):
	B,sgl = q
	N = len(B)
	sigma = np.array([[i] for i in range(N)])

	Q0 = 0
	Bt = deepcopy(B)
	while True:
		
		C,Q = Modulize(Bt,sgl)

		if Q<=Q0: break

		Q0 = Q
		R =get_comm(C)
		sigma = UpdateSigma(sigma,R)  
		Bt = renormlize(Bt,R)


	return to_Membership(sigma,N),Q
   #~ 
#~ def LoivenMod(B):
	#~ N = len(B)
	#~ sigma = np.array([[i] for i in xrange(N)])
	  #~ 
	#~ C,Q = Modulize(B)
	#~ R =get_comm(C)
	#~ sigma = UpdateSigma(sigma,R)
#~ 
	#~ return to_Membership(sigma,N),Q

def LouvainModM(B,n,sgl,ncpu):
	'Multicall (ncpu process) for loiven'
	if ncpu>1:
		p = Pool(ncpu)
		X = p.map(LouvainMod_Hier,zip([B]*n,[sgl]*n) )
		p.close()
	else:
		X = map(LouvainMod_Hier,zip([B]*n,[sgl]*n) )

	return max(X,key=lambda x:x[1])

def Find_Membership(XR,n=10,ncpu=1,method='Pos',sgl=1e-12,hierarchy=True):

	N,M = XR.shape
	A = np.corrcoef(XR)
	B,var = RMT(A,(N,M),method,rem_mode=False)

	H = [LouvainModM(B,n,sgl,ncpu)[0].astype(int)]

	V = [[(0,var)]]
	if hierarchy==False:
		return H

	while True:
		xvar = []
		M = H[-1]
		
		mx,h = 0,np.zeros(N)
		
		size = Counter(M)
		
		for c in set(M):
			if size[c]>1:
				Bs = deepcopy(B)
				As = A[np.where(M==c)[0],:][:,np.where(M==c)[0]]
				
				Bs,var = RMT(As,(As.shape[0],XR.shape[1]),method,rem_mode=True)
				Ms,q = LouvainModM(Bs,n,sgl,ncpu)
				h[np.where(M==c)] = Ms+mx
				xvar.append((c,var))
				mx = h.max()+1
			else:
				h[np.where(M==c)] = mx
				mx+=1

		if len(set(h))==len(set(H[-1])): break
		H.append(h.astype(int))
		V.append(xvar)
		
		if set(h)==N: break
	return H


def Find_Membership_AV(XR,n=10,ncpu=1,method='Pos',sgl=1e-12,hierarchy=True):
	
	N,M = XR.shape
	#A = np.corrcoef(XR)
	B,var = RMT_av(XR,(N,M),method,rem_mode=False)
	
	H = [LouvainModM(B,n,sgl,ncpu)[0].astype(int)]
	
	V = [[(0,var)]]
	if hierarchy==False:
		return H

	while True:
		xvar = []
		M = H[-1]
		
		mx,h = 0,np.zeros(N)
		
		size = Counter(M)
		
		for c in set(M):
			if size[c]>1:
				Bs = deepcopy(B)
				#As = A[np.where(M==c)[0],:][:,np.where(M==c)[0]]
				Xs = XR[np.where(M==c)[0]]
				Bs,var = RMT_av(Xs,(Xs.shape[0],Xs.shape[1]),method,rem_mode=True)
				Ms,q = LouvainModM(Bs,n,sgl,ncpu)
				h[np.where(M==c)] = Ms+mx
				xvar.append((c,var))
				mx = h.max()+1
			else:
				h[np.where(M==c)] = mx
				mx+=1

		if len(set(h))==len(set(H[-1])): break
		H.append(h.astype(int))
		V.append(xvar)
		
		if set(h)==N: break
	return H



	

