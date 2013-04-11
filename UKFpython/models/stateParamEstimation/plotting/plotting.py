import numpy as np
import matplotlib.pyplot as plt
from   pylab import figure

def plotResults(time,stopTime,X,Y,Z,U,Um,Xhat,Yhat,P,CovZ,Xsmooth,Psmooth):

	# plotting input and oputputs (real and measured)
	fig = plt.figure()
	ax1  = fig.add_subplot(211)
	ax1.plot(time,U[:,0],'b',label='$u$')
	ax1.plot(time,Um[:,0],'bx',label='$u_{m}$')
	ax1.set_xlabel('time [s]')
	ax1.set_ylabel('input')
	ax1.set_xlim([0, stopTime])
	ax1.legend()
	ax1.grid(True)

	ax1  = fig.add_subplot(212)
	ax1.plot(time,Y[:,0],'g',label='$y$')
	ax1.plot(time,Z[:,0],'gx',label='$y_{m}$')
	ax1.set_xlabel('time [s]')
	ax1.set_ylabel('output')
	ax1.set_xlim([0, stopTime])
	ax1.legend()
	ax1.grid(True)

	# plotting real state and its estimation
	fig2 = plt.figure()
	ax2  = fig2.add_subplot(211)
	ax2.plot(time,X[:,0],'b',label='$x_{real}$')
	ax2.plot(time,Xhat[:,0],'r--',label='$x_{UKF}$')
	ax2.plot(time,Xsmooth[:,0],'g--',label='$x_{SMOOTH}$')
	ax2.fill_between(time, Xsmooth[:,0]-2*np.sqrt(Psmooth[:,0,0]), Xsmooth[:,0] +2*np.sqrt(Psmooth[:,0,0]), facecolor='green', interpolate=True, alpha=0.3)
	ax2.set_xlabel('time [s]')
	ax2.set_ylabel('state')
	ax2.set_xlim([0, stopTime])
	ax2.legend()
	ax2.grid(True)

	ax2  = fig2.add_subplot(212)
	ax2.plot(time,X[:,1],'b',label='$b_{real}$')
	ax2.plot(time,Xhat[:,1],'r--',label='$b_{UKF}$')
	ax2.plot(time,Xsmooth[:,1],'g--',label='$x_{SMOOTH}$')
	ax2.fill_between(time, Xsmooth[:,1]-2*np.sqrt(Psmooth[:,1,1]), Xsmooth[:,1] +2*np.sqrt(Psmooth[:,1,1]), facecolor='green', interpolate=True, alpha=0.3)
	ax2.set_xlabel('time [s]')
	ax2.set_ylabel('parameter')
	ax2.set_xlim([0, stopTime])
	ax2.legend()
	ax2.grid(True)

	plt.show()