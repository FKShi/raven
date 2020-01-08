# Copyright 2017 Battelle Energy Alliance, LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""
Created on October 28, 2015

"""

from __future__ import division, print_function, unicode_literals, absolute_import
from PostProcessorInterfaceBaseClass import PostProcessorInterfaceBase
import os
import numpy as np
from scipy import interpolate
import copy


class dataObjectLabelFilter(PostProcessorInterfaceBase):
  """
   This Post-Processor filters out the points or histories accordingly to a chosen clustering label
  """
  def initialize(self):
    """
     Method to initialize the Interfaced Post-processor
     @ In, None,
     @ Out, None,

    """

    PostProcessorInterfaceBase.initialize(self)
    self.inputFormat  = None
    self.outputFormat = None
    self.label        = None
    self.clusterIDs   = None
    self.clusteringMethod = 'extended'  # if extended, the cluster label will be used to cluster over time
                                        # (=> only the portion of the history that matches the cluster IDs will be retrived),
                                        # otherwise it will be used to cluster the history based on
                                        # last values of the clusterIDs. Note: IT HAS MEANING FOR HISTORY SET ONLY!

  def readMoreXML(self,xmlNode):
    """
      Function that reads elements this post-processor will use
      @ In, xmlNode, ElementTree, Xml element node
      @ Out, None
    """

    for child in xmlNode:
      if child.tag == 'dataType':
        dataType = child.text
        if dataType in set(['HistorySet','PointSet']):
          self.inputFormat  = dataType
          self.outputFormat = dataType
        else:
          self.raiseAnError(IOError, 'dataObjectLabelFilter Interfaced Post-Processor ' +
                            str(self.name) + ' : dataType ' + str(dataType) +
                            ' is not recognized (available are HistorySet, PointSet)')
      elif child.tag == 'label':
        self.label = child.text.strip()
      elif child.tag == 'clusterIDs':
        self.clusterIDs = [int(clusterID.strip()) for clusterID in child.text.split(',')]
      elif child.tag =='clusteringMethod':
        self.clusteringMethod = child.text.strip()
        if self.clusteringMethod not in ['point', 'extended']:
          self.raiseAnError(IOError, '"clusteringMethod" must be one of :' +
                            ', '.join(['point', 'extended']) + '. Got: ' +
                            str(self.clusteringMethod) + '!')
      elif child.tag !='method':
        self.raiseAnError(IOError, 'dataObjectLabelFilter Interfaced Post-Processor ' +
                          str(self.name) + ' : XML node ' + str(child) + ' is not recognized')

  def run(self,inputDic):
    """
     Method to post-process the dataObjects
     @ In, inputDic, list, list of dictionaries which contains the data inside the input DataObjects
     @ Out, outputDic, dictionary, output dictionary to be provided to the base class
    """
    if len(inputDic)>1:
      self.raiseAnError(IOError, 'HistorySetSync Interfaced Post-Processor ' + str(self.name) + ' accepts only one dataObject')
    else:
      inputDict = inputDic[0]
      if self.label not in inputDict['data']:
        self.raiseAnError(IOError, 'Not found label ' + str(self.label) + ' in input dataObject!')
      outputDict = {}
      outputDict['data'] ={}
      outputDict['dims'] = {}
      outputDict['metadata'] = copy.deepcopy(inputDict['metadata']) if 'metadata' in inputDict.keys() else {}
      labelType = type(inputDict['data'][self.label][0])
      if labelType != np.ndarray:
        indexes = np.where(np.in1d(inputDict['data'][self.label],self.clusterIDs))[0]
        for key in inputDict['data'].keys():
          outputDict['data'][key] = inputDict['data'][key][indexes]
          outputDict['dims'][key] = []
      else:
        for key in inputDict['data'].keys():
          if type(inputDict['data'][key][0]) == np.ndarray:
            temp = []
            for cnt in range(len(inputDict['data'][self.label])):
              indexes = np.where(np.in1d(inputDict['data'][self.label][cnt],self.clusterIDs))[0]
              if len(indexes) > 0:
                if self.clusteringMethod == 'extended':
                  temp.append(copy.deepcopy(inputDict['data'][key][cnt][indexes]))
                else:
                  temp.append(copy.deepcopy(inputDict['data'][key][cnt]))
            outputDict['data'][key] = np.asanyarray(temp)
            outputDict['dims'][key] = []
          else:
            outputDict['data'][key] = np.empty(0)
            for cnt in range(len(inputDict['data'][self.label])):
              indexes = np.where(np.in1d(inputDict['data'][self.label][cnt],self.clusterIDs))[0]
              if len(indexes) > 0:
                outputDict['data'][key] = np.append(outputDict['data'][key], copy.deepcopy(inputDict['data'][key][cnt]))
              outputDict['dims'][key] = []
    return outputDict
