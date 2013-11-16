import numpy as np
from FmuUtils.FmuPool import FmuPool

class ukfFMU():
	"""
	This class represents an Unscented Kalman Filter (UKF) that can be used for the state and parameter estimation of nonlinear dynamic systems
	"""
	
	def __init__(self, model, augmented = False):
		"""
		Initialization of the UKF and its parameters. Provide the Model (FMU) as input
		
		The initialization assign these parameters then,
		
		1- compute the number of sigma points to be used
		2- define the parameters of the filter
		3- compute the weights associated to each sigma point
		4- initialize the constraints on the observed state variables
		 
		"""
		
		# set the model
		self.model = model
		
		# Instantiate the pool that will run the simulation in parallel
		self.pool = FmuPool(self.model, debug = False)
		
		# set the number of states variables (total and observed), parameters estimated and outputs
		self.n_state     = self.model.GetNumStates()
		self.n_state_obs = self.model.GetNumVariables()
		self.n_pars      = self.model.GetNumParameters()
		self.n_outputs   = self.model.GetNumMeasuredOutputs()
		self.augmented   = augmented
		if not augmented:
			self.N       = self.n_state_obs + self.n_pars
		else:
			self.N       = self.n_state_obs + self.n_pars + self.n_state_obs + self.n_pars + self.n_outputs
		
		# some check
		if self.n_state_obs > self.n_state:
			raise Exception('The number of observed states ('+str(self.n_state_obs)+') cannot be higher that the number of states ('+str(self.n_state)+')!')
		if self.n_pars < 0:
			raise Exception('The number of estimated parameters cannot be < 0')
		if self.n_outputs < 0:
			raise Exception('The number of outputs cannot be < 0')
		
		
		# compute the number of sigma points
		self.n_points    = 1 + 2*self.N

		# define UKF parameters with default values
		self.setUKFparams()
		
		# set the default constraints for the observed state variables (not active by default)
		self.ConstrStateHigh = np.empty(self.n_state_obs)
		self.ConstrStateHigh.fill(False)
		self.ConstrStateLow = np.empty(self.n_state_obs)
		self.ConstrStateLow.fill(False)
		# Max and Min Value of the states constraints
		self.ConstrStateValueHigh = np.zeros(self.n_state_obs)
		self.ConstrStateValueLow  = np.zeros(self.n_state_obs)
		
		# set the default constraints for the estimated parameters (not active by default)
		self.ConstrParsHigh = np.empty(self.n_pars)
		self.ConstrParsHigh.fill(False)
		self.ConstrParsLow = np.empty(self.n_pars)
		self.ConstrParsLow.fill(False)
		# Max and Min Value of the parameters constraints
		self.ConstrParsValueHigh = np.zeros(self.n_pars)
		self.ConstrParsValueLow  = np.zeros(self.n_pars)
	
	def __str__(self):
		"""
		This method returns a string that describe the object
		"""
		string  = "\nUKF algorithm for FMU model"
		string += "\nThe FMU model name is:                     "+self.model.GetFmuName()
		string += "\nThe total number of state variables is:    "+str(self.n_state)
		string += "\nThe number of state variables observed is: "+str(self.n_state_obs)
		string += "\nThe number of parameters estimated is:     "+str(self.n_pars)
		string += "\nThe number of outputs used to estimate is: "+str(self.n_outputs)
		return string
		
	
	def setDefaultUKFparams(self):
		"""
		This method set the default parameters of the UKF
		"""
		self.alpha    = 0.01
		self.k        = 1
		self.beta     = 2
		
		n = self.N
		
		self.lambd    = (self.alpha**2)*(n + self.k) - n
		self.sqrtC    = self.alpha*np.sqrt(n + self.k)
		
		# compute the weights
		self.computeWeights()

	def setUKFparams(self, alpha = 1.0/np.sqrt(3.0), beta = 2, k = None):
		"""
		This method set the non default parameters of the UKF
		"""
		self.alpha     = alpha
		self.beta      = beta
		
		n = self.N
		
		if k == None:
			self.k = 3 - n
		else:
			self.k = k
		
		self.lambd    = (self.alpha**2)*(n + self.k) - n
		self.sqrtC    = self.alpha*np.sqrt(self.k + n)
		
		# compute the weights
		self.computeWeights()
	
	def computeWeights(self):
		"""
		This method computes the weights of the UKF filter. These weights are associated to each sigma point and are used to
		compute the mean value (W_m) and the covariance (W_c) of the estimation
		"""
		
		n = self.N
		
		self.W_m       = np.zeros((1+2*n, 1))
		self.W_c       = np.zeros((1+2*n, 1))
		
		self.W_m[0,0]  = self.lambd/(n + self.lambd)
		self.W_c[0,0]  = self.lambd/(n + self.lambd) + (1 - self.alpha**2 + self.beta)

		for i in range(2*n):
			self.W_m[i+1,0] = 1.0/(2.0*(n + self.lambd))
			self.W_c[i+1,0] = 1.0/(2.0*(n + self.lambd))
	
	def getWeights(self):
		"""
		This method returns the vectors containing the weights for the UKF
		"""
		return (self.W_m, self.W_c)

	def squareRoot(self, A):
		"""
		This method computes the square root of a square matrix A, using the Cholesky factorization
		"""
		try:
			sqrtA = np.linalg.cholesky(A)
			return sqrtA

		except np.linalg.linalg.LinAlgError:
			print "Matrix "+str(A)+" is not positive semi-definite"
			return A	
	
	def constrainedState(self, X):
		"""
		This method apply the constraints to the state vector (only to the estimated states)
		"""		
		# Check for every observed state
		for i in range(self.n_state_obs):
		
			# if the constraint is active and the threshold is violated
			if self.ConstrStateHigh[i] and X[i] > self.ConstrStateValueHigh[i]:
				X[i] = self.ConstrStateValueHigh[i]
				
			# if the constraint is active and the threshold is violated	
			if self.ConstrStateLow[i] and X[i] < self.ConstrStateValueLow[i]:
				X[i] = self.ConstrStateValueLow[i]
				
		# Check for every observed state
		for i in range(self.n_pars):
		
			# if the constraint is active and the threshold is violated
			if self.ConstrParsHigh[i] and X[self.n_state+i] > self.ConstrParsValueHigh[i]:
				X[self.n_state+i] = self.ConstrParsValueHigh[i]
				
			# if the constraint is active and the threshold is violated	
			if self.ConstrParsLow[i] and X[self.n_state+i] < self.ConstrParsValueLow[i]:
				X[self.n_state+i] = self.ConstrParsValueLow[i]
		
		return X
				
	def computeSigmaPoints(self, x, pars, sqrtP, sqrtQ = None, sqrtR = None):
		"""
		This method computes the sigma points, Its inputs are
		
		* x     -- the state vector around the points will be propagated,
		* pars  -- the parameters that are eventually estimated
		* sqrtP -- the square root matrix of the covariance P (both observed states and estimated parameters),
				   that is used to spread the sigma points
		
		"""
		try:
			# reshape the state vector
			x = np.squeeze(x)
			x = x.reshape(1, self.n_state_obs)
		except ValueError:
			print "The vector of state variables has a wrong size"
			print x
			print "It should be long: "+str(self.n_state_obs)
			return np.array([])
		
		try:
			# reshape the parameter vector
			pars = np.squeeze(pars)
			pars = pars.reshape(1, self.n_pars)
		except ValueError:
			print "The vector of parameters has a wrong size"
			print pars
			print "It should be long: "+str(self.n_pars)
			return np.array([])
			
		# initialize the matrix of sigma points
		# the result is
		# [[0.0, 0.0, 0.0],
		#  [0.0, 0.0, 0.0],
		#  [0.0, 0.0, 0.0],
		#  [0.0, 0.0, 0.0],
		#      ....
		#  [0.0, 0.0, 0.0]]
		
		if self.augmented:
			Xs = np.zeros((self.n_points, self.n_state_obs + self.n_pars + self.n_state_obs + self.n_pars + self.n_outputs))
		else:
			Xs = np.zeros((self.n_points, self.n_state_obs + self.n_pars))

		# Now using the sqrtP matrix that is lower triangular:
		# create the sigma points by adding and subtracting the rows of the matrix sqrtP, to the lines of Xs
		# [[s11, 0  , 0  ],
		#  [s12, s22, 0  ],
		#  [s13, s23, s33]]
		
		if self.augmented:
			zerosQ = np.zeros((1, self.n_state_obs + self.n_pars))
			zerosR = np.zeros((1, self.n_outputs))
			xs0    = np.hstack((x, pars, zerosQ, zerosR))
			
			zero1 = np.zeros((self.n_state_obs+self.n_pars, self.n_state_obs + self.n_pars))
			zero2 = np.zeros((self.n_state_obs+self.n_pars, self.n_outputs))
			zero3 = np.zeros((self.n_state_obs+self.n_pars, self.n_outputs))
			
			row1 = np.hstack((sqrtP,   zero1,   zero2)) 
			row2 = np.hstack((zero1.T, sqrtQ,   zero3))
			row3 = np.hstack((zero2.T, zero3.T, sqrtR))
			sqrtP = np.vstack((row1, row2, row3))
		else:
			xs0 = np.hstack((x, pars))
			
		Xs[0,:] = xs0
		
		i = 1
		N = self.N
		for row in sqrtP:
			Xs[i,:]   = xs0
			Xs[i+N,:] = xs0
			
			nso = self.n_state_obs
			ns  = nso
			npa = self.n_pars
			
			try:
				
				if self.augmented:
					Xs[i,  0:nso]           += self.sqrtC*row[0:nso]
					Xs[i,  ns:ns+npa]        += self.sqrtC*row[ns:ns+npa]
					Xs[i,  ns+npa:ns+npa+nso] += self.sqrtC*row[ns+npa:ns+npa+nso]
					Xs[i,  ns+npa+nso:]      += self.sqrtC*row[ns+npa+nso:]
					
					Xs[i+N,  0:nso]           -= self.sqrtC*row[0:nso]
					Xs[i+N,  ns:ns+npa]        -= self.sqrtC*row[ns:ns+npa]
					Xs[i+N,  ns+npa:ns+npa+nso] -= self.sqrtC*row[ns+npa:ns+npa+nso]
					Xs[i+N,  ns+npa+nso:]      -= self.sqrtC*row[ns+npa+nso:]
				else:
					Xs[i,  0:nso]    += self.sqrtC*row[0:nso]
					Xs[i,  ns:ns+npa] += self.sqrtC*row[ns:]
					
					Xs[i+N,  0:nso]  -= self.sqrtC*row[0:nso]
					Xs[i+N,  ns:]    -= self.sqrtC*row[ns:]
					
			except ValueError:
				print "Is not possible to generate the sigma points..."
				print "the dimensions of the sqrtP matrix and the state and parameter vectors are not compatible"
				return Xs
			
			# TODO:
			# How to introduce constrained points
			# Xs[i,0:self.n_state_obs]                  = self.constrainedState(Xs[i,0:self.n_state_obs])
			# Xs[i+self.n_state_obs,0:self.n_state_obs] = self.constrainedState(Xs[i+self.n_state_obs,0:self.n_state_obs])
			Xs[i,:] = self.constrainedState(Xs[i,:])
			Xs[i+N,:] = self.constrainedState(Xs[i+N,:])
			
			i += 1
		
		return Xs

	def sigmaPointProj(self, Xs, t_old, t):
		"""
		
		This function, given a set of sigma points Xs, propagate them using the state transition function.
		The simulations are run in parallel if the flag parallel is set to True
		
		"""
		# initialize the vector of the NEW STATES
		X_proj = np.zeros((self.n_points, self.n_state_obs + self.n_pars))
		Z_proj = np.zeros((self.n_points, self.n_outputs))
		Xfull_proj = np.zeros((self.n_points, self.n_state))
		
		# from the sigma points, get the value of the states and parameters
		values = []
		for sigma in Xs:
			x = sigma[0:self.n_state_obs]
			pars = sigma[self.n_state_obs:self.n_state_obs+self.n_pars]
			temp = {"state":x, "parameters":pars}
			values.append(temp)

		# Run simulations in parallel
		poolResults = self.pool.Run(values, start = t_old, stop = t)
		
		i = 0
		for r in poolResults:
			time, results = r[0]
			
			X  = results["__ALL_STATE__"]
			Xo = results["__OBS_STATE__"]
			p  = results["__PARAMS__"]
			o  = results["__OUTPUTS__"]
			
			Xfull_proj[i,:] = X
			X_proj[i,0:self.n_state_obs] = Xo
			X_proj[i,self.n_state_obs:self.n_state_obs+self.n_pars] = p
			Z_proj[i,:] = o
			
			i += 1
			
		return X_proj, Z_proj, Xfull_proj

	def sigmaPointOutProj(self,m,Xs,u,t):
		"""
		This function computes the outputs of the model, given a set of sigma points Xs as well as inputs u and time step t
		"""
		# initialize the vector of the outputs
		Z_proj = np.zeros((self.n_points, self.n_outputs))
		
		#TODO: implement parallel 
		j = 0
		for x in Xs:
			Z_proj[j,:] = m.functionG(x, u, t, False)
			j += 1
		return Z_proj

	def averageProj(self,X_proj):
		"""
		This function averages the projection of the sigma points (both states and outputs)
		using a weighting vector W_m
		"""
		# make sure that the shape is [1+2*n, ...]
		X_proj.reshape(self.n_points, -1)
		
		# dot product of the two matrices
		avg = np.dot(self.W_m.T, X_proj)
		
		return avg

	def __AugStateFromFullState__(self, Xfull):
		"""
		Given a vector that contains all the state variables of the models and the parameters to be identified,
		this method returns a vector that contains the augmented and observed states:
		[ observed states, parameters estimated]
		"""
		return Xfull
		if False:
			row, col = np.shape(Xfull)
			Xaug = np.zeros((row, self.n_state_obs + self.n_pars + self.n_state_obs + self.n_outputs))
			
			nso = self.n_state_obs
			ns  = self.n_state 
			npa  = self.n_pars
			
			for i in range(row):
				Xaug[i, 0:nso]           = Xfull[i, 0:nso] 
				Xaug[i, ns:ns+npa]        = Xfull[i, ns:ns+npa]
				Xaug[i, ns+npa:ns+npa+nso] = Xfull[i, ns+npa:ns+npa+nso]
				Xaug[i, ns+npa+nso:]      = Xfull[i, ns+npa+nso:]
				
		else:
			row, col = np.shape(Xfull)
			Xaug = np.zeros((row, self.n_state_obs + self.n_pars))
			
			for i in range(row):
				Xaug[i, 0:self.n_state_obs]  = Xfull[i, 0:self.n_state_obs]
				Xaug[i, self.n_state_obs:]   = Xfull[i, self.n_state:self.n_state+self.n_pars]
				
		return Xaug

	def __newQ__(self, Q):
		"""
		This method, given the covariance matrix of the process noise (n_state_obs x n_state_obs)
		returns a new covariance matrix that has size (n_state_obs+n_pars x n_state_obs+n_pars)
		"""
		return Q
		nso = self.n_state_obs
		no  = self.n_outputs 
		npa  = self.n_pars
		if False:
			# create the new Q matrix to add
			A = np.zeros((nso, npa+nso+no))
			B = np.zeros((npa+nso+no, nso))
			C = np.zeros((npa+nso+no, npa+nso+no))
			top = np.hstack((Q, A))
			bot = np.hstack((B,C))
			newQ = np.vstack((top, bot))
		else:
			# create the new Q matrix to add
			A = np.zeros((nso, npa))
			B = np.zeros((npa, nso))
			C = np.zeros((npa, npa))
			top = np.hstack((Q, A))
			bot = np.hstack((B,C))
			newQ = np.vstack((top, bot))
		return newQ
		
	def computeP(self, X_p, Xa, Q):
		"""
		This function computes the state covariance matrix P as
		
		P[i,j] = W_c[i]*(Xs[i] - Xavg)^2 + Q[i,j]
		
		The vectors X_ contain the all the states (observed and not) and the estimated parameters.
		The non observed states should be removed, and then computing P which has size of (n_state_obs + n_pars).
		Note that Q has size n_state_obs, thus it has to be expanded with zero elements when added.
		
		"""
		# create a diagonal matrix containing the weights
		W = np.diag(self.W_c[:,0]).reshape(self.n_points, self.n_points)
		
		# subtract each sigma point with the average Xa, and tale just the augmented state
		V = self.__AugStateFromFullState__(X_p - Xa)
		
		# create the new Q matrix to add
		newQ = self.__newQ__(Q)
		
		# compute the new covariance matrix
		Pnew = np.dot(np.dot(V.T, W), V) + newQ
		return Pnew
		
	def computeCovZ(self, Z_p, Za, R):
		"""
		This function computes the output covariance matrix CovZ as
		
		CovZ[i,j] = W_c[i]*(Zs[i] - Zavg)^2 + R[i,j]
		
		"""
		W = np.diag(self.W_c[:,0]).reshape(self.n_points, self.n_points)

		V =  np.zeros(Z_p.shape)
		for j in range(self.n_points):
			V[j,:]   = Z_p[j,:] - Za[0]
		
		CovZ = np.dot(np.dot(V.T,W),V) + R
		return CovZ
	
	def computeCovXZ(self,X_p, Xa, Z_p, Za):
		"""
		This function computes the state-output cross covariance matrix (between X and Z)
		"""
		W = np.diag(self.W_c[:,0]).reshape(self.n_points,self.n_points)
			
		Vx = self.__AugStateFromFullState__(X_p - Xa)
		
		Vz = np.zeros(Z_p.shape)
		for j in range(self.n_points):
			Vz[j,:]   = Z_p[j,:] - Za[0]
	
		CovXZ = np.dot(np.dot(Vx.T,W),Vz)
		return CovXZ
	
	def computeS(self, X_proj, Xave, sqrtQ):
		"""
		This function computes the squared covariance matrix using QR decomposition + a Cholesky update
		"""
		# take the augmented states of the sigma points vectors
		# that are the observed states + estimated parameters
		X_proj_obs = self.__AugStateFromFullState__(X_proj)
		Xave_obs  = self.__AugStateFromFullState__(Xave)
		
		# Matrix of weights and signs of the weights
		weights = np.sqrt( np.abs(self.W_c[:,0]) )
		signs   = np.sign( self.W_c[:,0] )
		
		# create matrix A that contains the error between the sigma points and the average
		A     = np.array([[]])
		i     = 0
		for x in X_proj_obs:
			error = signs[i]*weights[i]*(x - Xave_obs)
			
			if i==1:
				A = error.T
			elif i>1:
				A = np.hstack((A,error.T))
			i    += 1
		
		# put on the side the matrix sqrtQ, that have to be modified to fit the dimension of the augmenets state	
		new_sqrtQ = self.__newQ__(sqrtQ)
		A = np.hstack((A,new_sqrtQ))
		
		# QR factorization
		q,L = np.linalg.qr(A.T,mode='full')
		
		# execute Cholesky update
		x = signs[0]*weights[0]*(X_proj_obs[0,] - Xave_obs)
		
		L = self.cholUpdate(L, x.T, self.W_c[:,0])
		
		return L
		
	def computeSy(self, Z_proj, Zave, sqrtR):
		"""
		This function computes the squared covariance matrix using QR decomposition + a Cholesky update
		"""
		# Matrix of weights and signs of the weights
		weights = np.sqrt( np.abs(self.W_c[:,0]) )
		signs   = np.sign( self.W_c[:,0] )
		
		# create matrix A that contains the error between the sigma points outputs and the average
		A     = np.array([[]])
		i     = 0
		for z in Z_proj:
			error = signs[i]*weights[i]*(z - Zave)
			if i==1:
				A = error.T
			elif i>1:
				A = np.hstack((A,error.T))
			i    += 1
			
		# put the square root R matrix on the side
		A = np.hstack((A,sqrtR))
		
		# QR factorization
		q,L = np.linalg.qr(A.T, mode='full')

		# NOW START THE CHOLESKY UPDATE
		z = signs[0]*weights[0]*(Z_proj[0,] - Zave)
		
		L = self.cholUpdate(L, z.T, self.W_c[:,0])
		
		return L
	
	def cholUpdate(self, L, X, W):
		"""
		This function computes the Cholesky update
		"""
		L = L.copy()
		weights = np.sqrt( np.abs( W ) )
		signs   = np.sign( W )
	
		# NOW START THE CHOLESKY UPDATE
		# DO IT FOR EACH COLUMN IN THE X MATRIX
		
		(row, col) = X.shape
		
		for j in range(col):
			x = X[0:,j]
			
			for k in range(row):
				rr_arg    = L[k,k]**2 + signs[0]*x[k]**2
				rr        = 0.0 if rr_arg < 0 else np.sqrt(rr_arg)
				c         = rr / L[k,k]
				s         = x[k] / L[k,k]
				L[k,k]    = rr
				L[k,k+1:] = (L[k,k+1:] + signs[0]*s*x[k+1:])/c
				x[k+1:]   = c*x[k+1:]  - s*L[k, k+1:]
				
		return L
	
	def computeCxx(self, X_next, X_now):
		"""
		This function computes the state-state cross covariance matrix (between the old Xold and the new Xnew state vectors).
		This is used by the smoothing process
		"""
		W = np.diag(self.W_c[:,0]).reshape(self.n_points,self.n_points)
		Xave_next = self.averageProj(X_next)
		Xave_now  = self.averageProj(X_now)
		
		Vnext = self.__AugStateFromFullState__(X_next - Xave_next)
		Vnow  = self.__AugStateFromFullState__(X_now - Xave_now)
	
		Cxx = np.dot(np.dot(Vnext.T, W), Vnow)
		return Cxx

	def ukf_step(self, x, sqrtP, sqrtQ, sqrtR, t_old, t, z = None, verbose=False):
		"""
		z,x,S,sqrtQ,sqrtR,u_old,u,
		
		This methods contains all the steps that have to be performed by the UKF:
		
		1- prediction
		2- correction and update
		"""
		print x
		pars = x[self.n_state_obs:]
		x = x[:self.n_state_obs]
		
		# the list of sigma points (each sigma point can be an array, containing the state variables)
		# x, pars, sqrtP, sqrtQ = None, sqrtR = None
		Xs      = self.computeSigmaPoints(x, pars, sqrtP, sqrtQ, sqrtR)
	
		if verbose:
			print "Sigma point Xs"
			print Xs
	
		# compute the projected (state) points (each sigma points is propagated through the state transition function)
		X_proj, Z_proj, Xfull_proj = self.sigmaPointProj(Xs,t_old,t)
		
		if verbose:
			print "Projected sigma points"
			print X_proj
	
		# compute the average
		Xave = self.averageProj(X_proj)
		Xfull_ave = self.averageProj(Xfull_proj)
		
		if verbose:
			print "Averaged projected sigma points"
			print Xave
		
		if verbose:
			print "Averaged projected full state"
			print Xfull_ave
		
		# compute the new squared covariance matrix S
		Snew = self.computeS(X_proj,Xave,sqrtQ)
		
		if verbose:
			print "New squared S matrix"
			print Snew
		
		# redraw the sigma points, given the new covariance matrix
		x    = Xave[0,0:self.n_state_obs]
		pars = Xave[0,self.n_state_obs:]
		Xs   = self.computeSigmaPoints(x, pars, Snew, sqrtQ, sqrtR)
		
		# Merge the real full state and the new ones
		self.model.SetState(Xfull_ave[0])
		
		if verbose:
			print "New sigma points"
			print Xs

		# compute the projected (outputs) points (each sigma points is propagated through the output function, this should not require a simulation,
		# just the evaluation of a function since the output can be directly computed if the state vector and inputs are known )
		X_proj, Z_proj, Xfull_proj = self.sigmaPointProj(Xs,t,t+1e-8)
		
		if verbose:
			print "Output projection of new sigma points"
			print Z_proj
			print "State re-projection"
			print X_proj

		# compute the average output
		Zave = self.averageProj(Z_proj)
		
		if verbose:
			print "Averaged output projection of new sigma points"
			print Zave

		# compute the innovation covariance (relative to the output)
		Sy = self.computeSy(Z_proj,Zave,sqrtR)
		
		if verbose:
			print "Output squared covariance matrix"
			print Sy
		
		# compute the cross covariance matrix
		CovXZ = self.computeCovXZ(X_proj, Xave, Z_proj, Zave)
		
		if verbose:
			print "State output covariance matrix"
			print CovXZ
	
		# Data assimilation step
		# The information obtained in the prediction step are corrected with the information
		# obtained by the measurement of the outputs
		# In other terms, the Kalman Gain (for the correction) is computed
		firstDivision = np.linalg.lstsq(Sy.T,CovXZ.T)[0]
		K             = np.linalg.lstsq(Sy, firstDivision)[0]
		K             = K.T
		
		# Read the output value
		if z == None:
			z = self.model.GetMeasuredDataOuputs(t)
		
		if verbose:
			print "Measured Output data to be compared against simulations"
			print z
		
		# State correction using the measurements
		X_corr = Xave + np.dot(K,z.reshape(self.n_outputs,1)-Zave.T).T
		
		# If constraints are active, they are imposed in order to avoid the corrected value to fall outside
		X_corr[0,:] = self.constrainedState(X_corr[0,:])
		
		if verbose:
			print "New state corrected"
			print X_corr
			raw_input("?")
		
		# The covariance matrix is corrected too
		U      = np.dot(K,Sy)
		S_corr = self.cholUpdate(Snew,U,-1*np.ones(self.n_state))
		
		# Apply the corrections to the model and then returns
		# Set observed states and parameters
		self.model.SetStateSelected(X_corr[0,:self.n_state_obs])
		self.model.SetParametersSelected(X_corr[0,self.n_state_obs:])
		
		return (X_corr[0], S_corr, Zave, Sy)
	
	def filter(self, start, stop, verbose=False):
		"""
		This method starts the filtering process and performs a loop of ukf-steps
		"""
		# Read the output measured data
		measuredOuts = self.model.GetMeasuredOutputDataSeries()
		
		# Get the number of time steps
		Ntimes = len(measuredOuts)
		
		# Initial conditions and other values
		x = [np.hstack((self.model.GetStateObservedValues(), self.model.GetParametersValues()))]
		sqrtP = [self.model.GetCovMatrixStatePars()]
		sqrtQ = self.model.GetCovMatrixStatePars()
		sqrtR = self.model.GetCovMatrixOutputs()
		
		for i in range(1,Ntimes):
			t_old = measuredOuts[i-1,0]
			t = measuredOuts[i,0]
			z = measuredOuts[i,1:]
			X_corr, sP, Zave, Sy = self.ukf_step(x[i-1], sqrtP[i-1], sqrtQ, sqrtR, t_old, t, z, verbose=verbose)
			
			x.append(X_corr)
			sqrtP.append(sP)
			
			print X_corr
			print Zave
			
		return
		
	
	def smooth(self,time,Xhat,S,sqrtQ,U,m,verbose=False):
		"""
		This methods contains all the steps that have to be performed by the UKF Smoother.
		"""
		# initialize the smoothed states and covariance matrix
		# the initial value of the smoothed state estimation are equal to the filtered ones
		Xsmooth = Xhat.copy()
		Ssmooth = S.copy()
		
		# get the number of time steps		
		s = np.reshape(time,(-1,1)).shape
		nTimeStep = s[0]

		# iterating starting from the end and back
		# i : nTimeStep-2 -> 0
		#
		# From point i with an estimation Xave[i], and S[i]
		# new sigma points are created and propagated, the result is a 
		# new vector of states X[i+1] (one for each sigma point)
		#
		# NOTE that at time i+1 there is available a corrected estimation of the state Xcorr[i+1]
		# thus the difference between these two states is back-propagated to the state at time i
		for i in range(nTimeStep-2,-1,-1):
			# actual state estimation and covariance matrix
			x_i = Xsmooth[i,:]
			S_i = Ssmooth[i,:,:]

			# compute the sigma points
			Xs_i        = self.computeSigmaPoints(x_i,S_i)
			
			if verbose:
				print "Sigma points"
				print Xs_i
			
			# mean of the sigma points
			Xs_i_ave    = self.averageProj(Xs_i)
			
			if verbose:
				print "Mean of the sigma points"
				print Xs_i_ave
			
			# propagate the sigma points
			x_plus_1    = self.sigmaPointProj(m,Xs_i,U[i],U[i+1],time[i],time[i+1])
			
			if verbose:
				print "Propagated sigma points"
				print x_plus_1
			
			# average of the sigma points
			Xave_plus_1 = self.averageProj(x_plus_1)
			
			if verbose:
				print "Averaged propagated sigma points"
				print Xave_plus_1
			
			# compute the new covariance matrix
			Snew = self.computeS(x_plus_1,Xave_plus_1,sqrtQ)
			
			if verbose:
				print "New Squared covaraince matrix"
				print Snew
			
			# compute the cross covariance matrix of the two states
			# (new state already corrected, coming from the "future", and the new just computed through the projection)
			Cxx  = self.computeCxx(x_plus_1,Xave_plus_1,Xs_i,Xs_i_ave)
			
			if verbose:
				print "Cross state-state covariance matrix"
				print Cxx
			
			# gain for the back propagation
			firstDivision = np.linalg.lstsq(Snew.T, Cxx.T)[0]
			D             = np.linalg.lstsq(Snew, firstDivision)[0]
			D             = D.T
			
			if verbose:
				print "Old state"
				print Xhat[i,:]
				print "Error:"
				print Xsmooth[i+1,0:self.n_state_obs] - Xave_plus_1[0,0:self.n_state_obs]
				print "Correction:"
				print np.dot(D, Xsmooth[i+1,0:self.n_state_obs] - Xave_plus_1[0,0:self.n_state_obs])
				
			# correction (i.e. smoothing, of the state estimation and covariance matrix)
			Xsmooth[i,self.n_state_obs:]   = Xhat[i,self.n_state_obs:]
			Xsmooth[i,0:self.n_state_obs]  = Xhat[i,0:self.n_state_obs] + np.dot(D, Xsmooth[i+1,0:self.n_state_obs] - Xave_plus_1[0,0:self.n_state_obs])
			
			# How to introduce constrained estimation
			Xsmooth[i,0:self.n_state_obs]  = self.constrainedState(Xsmooth[i,0:self.n_state_obs])
			
			if verbose:
				print "New smoothed state"
				print Xsmooth[i,:]
				raw_input("?")
			
			V              = np.dot(D,Ssmooth[i+1,:,:] - Snew)
			Ssmooth[i,:,:] = self.cholUpdate(S[i,:,:],V,-1*np.ones(self.n_state_obs))
			
		return (Xsmooth, Ssmooth)