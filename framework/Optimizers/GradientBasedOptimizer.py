"""
  This module contains the Gradient Based Optimization strategy

  Created on June 16, 2016
  @author: chenj
"""
#for future compatibility with Python 3--------------------------------------------------------------
from __future__ import division, print_function, unicode_literals, absolute_import
import warnings
warnings.simplefilter('default',DeprecationWarning)
#if not 'xrange' in dir(__builtins__): xrange = range
#End compatibility block for Python 3----------------------------------------------------------------

#External Modules------------------------------------------------------------------------------------
import sys
import os
import copy
import abc
import numpy as np
#External Modules End--------------------------------------------------------------------------------

#Internal Modules------------------------------------------------------------------------------------
from .Optimizer import Optimizer
from Assembler import Assembler
#Internal Modules End--------------------------------------------------------------------------------

class GradientBasedOptimizer(Optimizer):
  """
    This is the base class for gradient based optimizer. The following methods need to be overridden by all derived class
    self.localLocalInputAndChecks(self, xmlNode)
    self.localLocalInitialize(self, solutionExport = None)
    self.localCheckConvergence(self, convergence = False)
    self.localLocalGenerateInput(self,model,oldInput)
    self.localEvaluateGradient(self, optVarsValues, gradient = None)
  """
  def __init__(self):
    """
      Default Constructor that will initialize member variables with reasonable
      defaults or empty lists/dictionaries where applicable.
      @ In, None
      @ Out, None
    """
    Optimizer.__init__(self)
    self.constraintHandlingPara = {}                  # Dict containing parameters for parameters related to constraints handling
    self.gradDict = {}                                # Dict containing information for gradient related operations
    self.gradDict['numIterForAve'] = 1                # Number of iterations for gradient estimation averaging
    self.gradDict['pertNeeded'] = 1                   # Number of perturbation needed to evaluate gradient
    self.gradDict['pertPoints'] = {}                  # Dict containing inputs sent to model for gradient evaluation
    self.counter['perturbation'] = 0                  # Counter for the perturbation performed.
    self.counter['solutionUpdate'] = 0                # Counter for the solution exported.
    self.readyVarsUpdate = None                       # Bool variable indicating the finish of gradient evaluation and the ready to update decision variables

  def localInputAndChecks(self, xmlNode):
    """
      Method to read the portion of the xml input that belongs to all gradient based optimizer only
      and initialize some stuff based on the inputs got
      @ In, xmlNode, xml.etree.ElementTree.Element, Xml element node
      @ Out, None
    """
    self.gradDict['numIterForAve'] = int(self.paramDict.get('numGradAvgIterations', 1))
    self.localLocalInputAndChecks(xmlNode)

  @abc.abstractmethod
  def localLocalInputAndChecks(self, xmlNode):
    """
      Local method for additional reading.
      @ In, xmlNode, xml.etree.ElementTree.Element, Xml element node
      @ Out, None
    """
    pass # to be overwritten by subclass

  def localInitialize(self,solutionExport=None):
    """
      Method to initialize settings that belongs to all gradient based optimizer
      @ In, solutionExport, DataObject, optional, a PointSet to hold the solution
      @ Out, None
    """
    self.gradDict['pertPoints'] = {}

    #specializing the self.localLocalInitialize()
    if solutionExport != None : self.localLocalInitialize(solutionExport=solutionExport)
    else                      : self.localLocalInitialize()

  @abc.abstractmethod
  def localLocalInitialize(self, solutionExport = None):
    """
      Method to initialize local settings.
      @ In, solutionExport, DataObject, optional, a PointSet to hold the solution
      @ Out, None
    """
    pass

  def localStillReady(self,ready, convergence = False): #,lastOutput=None
    """
      Determines if optimizer is ready to provide another input.  If not, and if jobHandler is finished, this will end sampling.
      @ In, ready, bool, variable indicating whether the caller is prepared for another input.
      @ In, convergence, bool, optional, variable indicating whether the convergence criteria has been met.
      @ Out, ready, bool, boolean variable indicating whether the caller is prepared for another input.
    """
    if ready == False:
      return ready # Return if we exceed the max iterations or converges...
    if self.mdlEvalHist == None and self.counter['perturbation'] < self.gradDict['pertNeeded']:
      return ready # Return if we just initialize
    elif self.mdlEvalHist.isItEmpty() and self.counter['perturbation'] < self.gradDict['pertNeeded']:
      return ready # Return if we just initialize
    elif self.counter['perturbation'] >= self.gradDict['pertNeeded']:
      if len(self.mdlEvalHist) % (self.gradDict['pertNeeded']+1): ready = False

    ready = self.localLocalStillReady(ready, convergence)

    return ready

  @abc.abstractmethod
  def localLocalStillReady(self, ready, convergence = False):
    """
      Determines if optimizer is ready to provide another input.  If not, and if jobHandler is finished, this will end sampling.
      @ In, ready, bool, variable indicating whether the caller is prepared for another input.
      @ In, convergence, bool, optional, variable indicating whether the convergence criteria has been met.
      @ Out, ready, bool, boolean variable indicating whether the caller is prepared for another input.
    """
    pass

  def localGenerateInput(self,model,oldInput):
    """
      Method to generate input for model to run
      @ In, model, model instance, it is the instance of a RAVEN model
      @ In, oldInput, list, a list of the original needed inputs for the model (e.g. list of files, etc. etc)
      @ Out, None
    """
    if self.counter['mdlEval'] > 1:
      if self.counter['perturbation'] < self.gradDict['pertNeeded']:
        self.readyVarsUpdate = False
        self.counter['perturbation'] += 1
      else: # Got enough perturbation
        self.readyVarsUpdate = True
        self.counter['perturbation'] = 0
        self.counter['varsUpdate'] += 1
    else:
      self.readyVarsUpdate = False

    self.localLocalGenerateInput(model,oldInput)

  @abc.abstractmethod
  def localLocalGenerateInput(self,model,oldInput):
    """
      This class need to be overwritten since it is here that the magic of the optimizer happens.
      After this method call the self.inputInfo should be ready to be sent to the model
      @ In, model, model instance, it is the instance of a RAVEN model
      @ In, oldInput, list, a list of the original needed inputs for the model (e.g. list of files, etc. etc)
      @ Out, None
    """
    pass

  def evaluateGradient(self, optVarsValues):
    """
      Method to evaluate gradient based on perturbed points and model evaluations.
      @ In, optVarsValues, dict, dictionary containing perturbed points.
                                 optVarsValues should have the form {pertIndex: {varName: [varValue1 varValue2]}}
                                 Therefore, each optVarsValues[pertIndex] should return a dict of variable values
                                 that is sufficient for gradient evaluation for at least one variable
                                 (depending on specific optimization algorithm)
      @ Out, gradient, dict, dictionary containing gradient estimation. gradient should have the form {varName: gradEstimation}
    """
    gradArray = {}
    for var in self.optVars:                      gradArray[var] = np.ndarray((0,0))

    # Evaluate gradient at each point
    for pertIndex in optVarsValues.keys():
      tempDictPerturbed = optVarsValues[pertIndex]
      tempDictPerturbed['lossValue'] = copy.copy(self.lossFunctionEval(tempDictPerturbed))
      lossDiff = tempDictPerturbed['lossValue'][0] - tempDictPerturbed['lossValue'][1]
      for var in self.optVars:
        if tempDictPerturbed[var][0] != tempDictPerturbed[var][1]:
          gradArray[var] = np.append(gradArray[var], lossDiff/(tempDictPerturbed[var][0]-tempDictPerturbed[var][1])*1.0)

    gradient = {}
    for var in self.optVars:
      gradient[var] = gradArray[var].mean()

    gradient = self.localEvaluateGradient(optVarsValues, gradient)
    return gradient

  def localEvaluateGradient(self, optVarsValues, gradient = None):
    """
      Local method to evaluate gradient.
      @ In, optVarsValues, dict, dictionary containing perturbed points.
                                 optVarsValues should have the form {pertIndex: {varName: [varValue1 varValue2]}}
                                 Therefore, each optVarsValues[pertIndex] should return a dict of variable values
                                 that is sufficient for gradient evaluation for at least one variable
                                 (depending on specific optimization algorithm)
      @ In, gradient, dict, optional, dictionary containing gradient estimation by the caller.
                                      gradient should have the form {varName: gradEstimation}
      @ Out, gradient, dict, dictionary containing gradient estimation. gradient should have the form {varName: gradEstimation}
    """
    return gradient

  def localCheckConvergence(self, convergence = False):
    """
      Local method to check convergence.
      @ In, convergence, bool, optional, variable indicating how the caller determines the convergence.
      @ Out, convergence, bool, variable indicating whether the convergence criteria has been met.
    """
    return convergence

  def localCheckConstraint(self, optVars, satisfaction = True):
    """
      Local method to check whether a set of decision variables satisfy the constraint or not
      @ In, optVars, dict, dictionary containing the value of decision variables to be checked, in form of {varName: varValue}
      @ In, satisfaction, bool, optional, variable indicating how the caller determines the constraint satisfaction at the point optVars
      @ Out, satisfaction, bool, variable indicating the satisfaction of constraints at the point optVars
    """
    return satisfaction

  def localFinalizeActualSampling(self,jobObject,model,myInput):
    """
      Overwrite only if you need something special at the end of each run....
      This function is used by optimizers that need to collect information from the just ended run
      @ In, jobObject, instance, an instance of a JobHandler
      @ In, model, model instance, it is the instance of a RAVEN model
      @ In, myInput, list, the generating input
    """
    if self.solutionExport != None and len(self.mdlEvalHist) > 0:
      while self.counter['solutionUpdate'] <= self.counter['varsUpdate']:
        solutionExportUpdatedFlag = False
        prefix = self.mdlEvalHist.getMetadata('prefix')
        # This MR does not include multiple trajectory, use following simple solution
        # This will be replaced by "smart prefix management that is included in next MR that comes with parallel trajectory"  
        pre = str((self.counter['solutionUpdate'])*(self.gradDict['pertNeeded']+1)+1)
        for index, pr in enumerate(prefix):
          if pr.split('|')[-1] == pre:
            solutionExportUpdatedFlag = True
            break
        
        if solutionExportUpdatedFlag:
          inputeval=self.mdlEvalHist.getParametersValues('inputs', nodeId = 'RecontructEnding')
          outputeval=self.mdlEvalHist.getParametersValues('outputs', nodeId = 'RecontructEnding')
          # update solution export
          for var in self.solutionExport.getParaKeys('inputs'):
            if var in self.optVars:
              self.solutionExport.updateInputValue(var,inputeval[var][index])
          if 'varsUpdate' in self.solutionExport.getParaKeys('inputs'):
            self.solutionExport.updateInputValue('varsUpdate', np.asarray([self.counter['solutionUpdate']]))
          for var in self.solutionExport.getParaKeys('outputs'):
            if var == self.objVar:
              self.solutionExport.updateOutputValue(var, outputeval[var][index])
          self.counter['solutionUpdate'] += 1
        else:
          break