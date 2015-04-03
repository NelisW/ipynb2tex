#!/usr/bin/python2
"""Notebook to  LaTeX and PDF

http://ipython.org/ipython-doc/3/notebook/nbformat.html#nbformat
http://ipython.org/ipython-doc/3/whatsnew/version3.html

Usage: ipnb2tex.py [<ipnbfilename>] [<outfilename>]  [<imagedir>]
"""

from __future__ import print_function, division

import os
import io
import base64
import shutil
import re
import itertools
import operator
import unicodedata
import os.path, fnmatch
# from IPython.nbformat import current as ipnbcurrent
import IPython.nbformat as nbformat
import docopt
import lxml.html
import markdown
from lxml import etree as ET
import numpy as np

# need the following four lines to print unicode to sysout
import sys
import codecs
sys.stdout = codecs.getwriter('utf8')(sys.stdout)
sys.stderr = codecs.getwriter('utf8')(sys.stderr)

nbformat
#list of bibtex entries to be built up in this file
bibtexlist = []
#dict of bibtex label crossreferences between local and existing bibtex files.
bibxref = {}

""" The ipnb2tex.py reads the IPython notebook and converts it to a \LaTeX{} set of files 
(a *.tex file and a number of images). The script is invoked as follows:

python ipnb2tex.py file.ipynb file.tex imagedir

where

    file.ipynb [optional] is the name of the input IPython notebook file. 
    If no input filename is supplied, all .ipynb files in current directory will be processed. 
    In this event the output filenames will be the same as the .ipynb files, just with a tex filetype.

    file.tex [optional] is the name of output \LaTeX{} file. If none is given the output 
    filename will be the same as the input file, but with the .tex extension.

    imagedir [optional] is the directory where images are written to. If not given, 
    this image directory will be the ./pic directory.


"""

standardHeader =\
r"""
\documentclass[english]{workpackage}[1996/06/02]

% input the common preamble content (required by the ipnb2latex converter)
\input{header.tex}

% then follows the rest of the preamble to be placed before the begin document
% this preamble content is special to the documentclass you defined above.
\WPproject{}           % project name
\WPequipment{}         % equipment name
\WPsubject{}           % main heading 
\WPconclusions{} 
\WPclassification{} 
\WPdocauthor{}
\WPcurrentpackdate{\today}
\WPcurrentpacknumber{} % work package number
\WPdocnumber{}         % this doc number hosts all the work packages
\WPprevpackdate{}      % work package which this one supersedes
\WPprevpacknumber{}    % work package which this one supersedes
\WPsuperpackdate{}     % work package which comes after this one
\WPsuperpacknumber{}   % work package which comes after this one
\WPdocontractdetails{false}
\WPcontractname{}      % contract name 
\WPorderno{}           % contract order number
\WPmilestonenumber{}   % contract milestone number
\WPmilestonetitle{}    % contract milestone title
\WPcontractline{}      % contract milestone line number 
\WPdocECPnumber{}      % ecp/ecr number
\WPdistribution{}

%and finally the document begin.
\begin{document}
\WPlayout
"""
################################################################################
#lists the files in a directory and subdirectories (from Python Cookbook)
def listFiles(root, patterns='*', recurse=1, return_folders=0):
    # Expand patterns from semicolon-separated string to list
    pattern_list = patterns.split(';')
    # Collect input and output arguments into one bunch
    class Bunch:
        def __init__(self, **kwds): self.__dict__.update(kwds)
    arg = Bunch(recurse=recurse, pattern_list=pattern_list,
        return_folders=return_folders, results=[])

    def visit(arg, dirname, files):
        # Append to arg.results all relevant files (and perhaps folders)
        for name in files:
            fullname = os.path.normpath(os.path.join(dirname, name))
            if arg.return_folders or os.path.isfile(fullname):
                for pattern in arg.pattern_list:
                    if fnmatch.fnmatch(name, pattern):
                        arg.results.append(fullname)
                        break
        # Block recursion if recursion was disallowed
        if not arg.recurse: files[:]=[]
    os.path.walk(root, visit, arg)
    return arg.results


################################################################################
def latexEscapeForHtmlTableOutput(string):

  # string = string.replace('_', '\\_')

  #first remove escaped \% if present, then do escape again on all % present
  string = string.replace('\\%','%')
  string = string.replace('%','\\%')

  for mathcar in ['<', '>', '|', '=']:
    string = string.replace(mathcar, '$'+mathcar+'$')
  #replace computer-style float with scientific notation    
  matches = re.search(r'^([0-9,.,\-]+)e(\+|\-)([0-9]+)$', string.strip())
  if matches:
    lead, sign, pw = matches.groups()
    sign = sign.replace('+', '')
    string = string.replace(matches.group(), lead + r'\times 10^{' + sign + pw.strip('0') + '}')
  return string


################################################################################
def pptree(e):
    print(ET.tostring(e, pretty_print=True))
    print

################################################################################
def convertHtmlTable(html, cell, table_index=0):

  if not (isinstance(html, basestring)):
    html = lxml.html.tostring(html)

  if not "<div" in  html:   
    html = "<div>" + html + "</div>"

  html = html.replace("<thead>", "").replace("</thead>", "").replace("<tbody>", "").replace("</tbody>", "")
  # html = html.replace('overflow:auto;','').replace(' style="max-height:1000px;max-width:1500px;','')
  tree = lxml.html.fromstring(html)

  # print('pptree-html')
  # pptree(tree)


  # for tags in tree.getiterator():
  #   print(tags.tag, tags.text)


  rtnString = ''
  for table in tree.findall("table"):

    # first lets traverse it and look for rowspan/colspans, find the shape
    row_counts = len(table.findall('tr'))
    col_counts = [0] * row_counts
    for ind, row in enumerate(table.findall('tr')):
      for tag in row:
        if not (tag.tag == 'td' or tag.tag == 'th'): continue
        if 'colspan' in tag.attrib:
            col_counts[ind] += int(tag.attrib['colspan']) - 1
        if 'rowspan' in tag.attrib:
          for j in range(int(tag.attrib['rowspan'])):
            col_counts[ind+j] += 1
        else:
          col_counts[ind] += 1
    if len(set(col_counts)) != 1: 
      raise ValueError('inconsistent number of column counts')
    col_counts = col_counts[0]

    # print(row_counts, col_counts)

    if row_counts == 0 or col_counts == 0:
      continue

    #first determine arrays of colspan and row span
    # these arrays have nonzero values in spanned cell, no data here
    rowspan = np.zeros((row_counts, col_counts), dtype=np.int)
    colspan = np.zeros((row_counts, col_counts), dtype=np.int)
    irow = 0
    for row in table.findall('tr'):
      icol = 0
      for col in row:
        if col.tag != 'td' and col.tag != 'th':
          raise NotImplementedError('Expecting either TD or TH tag under row')
        if rowspan[irow,icol] != 0:
          colspan[irow,icol] = 0
          icol += 1
        colspan[irow,icol] = 0
        icol += 1
        if 'colspan' in col.attrib:
          icolspan = int(col.attrib['colspan'])

          for i in range(1,icolspan):
            colspan[irow,icol] = 1
            icol += 1 
        if 'rowspan' in col.attrib:
          rowspan[irow,icol-1] = 0
          for i in range(1, int(col.attrib['rowspan'])):
            rowspan[irow+i,icol-1] = int(col.attrib['rowspan'])-i
      irow += 1

    # print('colspan=\n{}\n'.format(colspan))
    # print('rowspan=\n{}\n'.format(rowspan))

    formatStr = getMetaDataString(cell, table_index, 'tableCaption', 'format','')
    if not formatStr:
      formatStr = '|' + "|".join(['c'] * col_counts) + '|'


    terminator = '&'
    latexTabular = ""
    latexTabular += "\n\\begin{{tabular}}{{{}}}\n".format(formatStr)
    latexTabular += "\\hline\n"
    irow = 0
    for row_index, row in enumerate(table.findall('tr')):
      icol = 0
      for col_index, col in enumerate(row):
        while rowspan[irow,icol]:
          latexTabular += '&'
          icol += 1

        txt = latexEscapeForHtmlTableOutput(unicode(col.text_content()).strip())
        if 'colspan' in col.attrib:
          icolspan = int(col.attrib['colspan'])
          txt = '\multicolumn{{{}}}{{|c|}}{{{}}}'.format(icolspan,txt)
        latexTabular += txt + '&'
        while(colspan[irow,icol]):
          icol += 1
        icol += 1
      #calculate the clines
      if irow==0 or irow==row_counts-1:
        hline = r'\hline'
      else:
        if np.count_nonzero(rowspan[irow+1,:])==0:
          hline = r'\hline'
        else:
          hline = ''
          clines =  1 - rowspan[irow+1,:]
          for i in range(0,clines.shape[0]):
            if clines[i] > 0:
              hline += '\\cline{{{}-{}}}'.format(i+1,i+1)
      irow += 1
      latexTabular = latexTabular[:-1] + '\\\\'+hline
      latexTabular += '\n'
    latexTabular += "\n"
    latexTabular += "\\end{tabular}\n"


    #process the caption string, either a string or a list of strings
    captionStr = getMetaDataString(cell, table_index, 'tableCaption', 'caption','')
    fontsizeStr = getMetaDataString(cell, table_index, 'tableCaption', 'fontsize','normalsize')
    labelStr = getMetaDataString(cell, table_index, 'tableCaption', 'label','')
    if labelStr:
      labelStr = '\\label{{{}-{}}}'.format(labelStr, table_index)

    texStr = ''
    if captionStr:
      texStr += '\n\\begin{table}[htb]\n'
      texStr += '\\centering\n'
      texStr += '\\caption{'+'{}{}'.format(captionStr,labelStr)+'}\n'
    else:
       texStr += '\\begin{center}\n'

    texStr += "\n\\begin{{{}}}\n".format(fontsizeStr)
    texStr += latexTabular
    texStr += "\\end{{{}}}\n".format(fontsizeStr)

    if captionStr:
      texStr += '\\end{table}\n\n'
    else:
      texStr += '\\end{center}\n\n'

    table_index += 1
    rtnString += texStr

  return rtnString


################################################################################
def findAllStr(string, substr):
  ind = string.find(substr)
  while ind >= 0:
    yield ind
    ind = string.find(substr, ind+1)


################################################################################
def findNotUsedChar(string):
  delims = '~!@#$%-+=:;'


################################################################################
def processVerbatim(child):
  childtail = '' if child.tail==None else child.tail
  #multiline text must be in verbatim environment, not just \verb++
  if len(child.text.splitlines()) > 1:
    strVerb =  r'\begin{verbatim}' + '\n' + child.text + r'\end{verbatim}' + childtail
  else:
    strVerb =  r'\verb+' + child.text.rstrip() + r'+' + childtail
  return strVerb




################################################################################
def processParagraph(pnode):
  tmp = ""
  if pnode.text:
    tmp += pnode.text
  for child in pnode:
    # print('child.tag={}'.format(child.tag))
    # print('child.text={}'.format(child.text))
    # print('child.tail={}'.format(child.tail))

    childtail = '' if child.tail==None else child.tail

    # if child.tag == 'ul':
    #   if len(child.getchildren()) > 0:
    #     raise ValueError('need to learn to deal with nested children in <p>',
    #         pnode, child, child.getchildren())



    if child.tag == 'em':
      tmp += r"\textit{" + child.text + "}" + childtail

    elif child.tag == 'i':
      tmp += r"\textit{" + child.text + "}" + childtail

    elif child.tag == 'b':
      tmp += r"\textbf{" + child.text + "}" + childtail

    #this call may be recursive for nested lists
    elif child.tag == 'ul' or child.tag == 'ol':
      tmp += processList(child) + '\n'

    elif child.tag == 'p':
      tmp += processParagraph(child).strip() + '\n\n' + childtail

    elif child.tag == 'br':
      tmp += "\n\n" + childtail

    elif child.tag == 'code':
      tmp += processVerbatim(child)

    elif child.tag == 'strong':
      tmp +=  r"\textbf{" + child.text + "}" + childtail
      
    elif child.tag == 'font':
      #currently ignore font attributes
      tmp +=  child.text + childtail
      
    elif child.tag == 'a':
      url = child.get('href')
      if url is not None:
        citelabel = cleanFilename(url,  removestring =" %:/,.\\[]=?~!@#$^&*()-_{};")
        if citelabel in bibxref.keys():
          pass
          # tmp +=  child.text + r'\cite{{{0}}}'.format(bibxref[citelabel]) + childtail
        else:
          bibxref[citelabel] = citelabel
          # raise ValueError('This key is not in the bibxref dict metadata:', citelabel)

        url = r'\url{'+url+'}'
        # print('****',url)
        bibtexentry = '@MISC{{{0},\n'.format(bibxref[citelabel]) + \
            '  url = {{{0}}}\n}}\n\n'.format(url)
        bibtexlist.append(bibtexentry)
        # print('\nchild.text={}\nlabel={}\ntail={}\n'.format(child.text, r'\cite{{{0}}}'.format(bibxref[citelabel]), childtail))
        if child.text:
          childtext = child.text
          if 'http' in childtext:
            childtext = r'\url{'+childtext+'}'
          tmp +=  childtext
        tmp +=  r'\cite{{{0}}}'.format(bibxref[citelabel]) + childtail


    else:
      raise ValueError('need to learn to process this:', child.tag)
  if pnode.tail:
    tmp += pnode.tail
  return tmp.strip() + '\n\n'

################################################################
def cleanFilename(sourcestring,  removestring =" %:/,.\\[]"):
    """Clean a string by removing selected characters.

    Creates a legal and 'clean' source string from a string by removing some 
    clutter and  characters not allowed in filenames.
    A default set is given but the user can override the default string.

    Args:
        | sourcestring (string): the string to be cleaned.
        | removestring (string): remove all these characters from the string (optional).

    Returns:
        | (string): A cleaned-up string.

    Raises:
        | No exception is raised.
    """
    #remove the undesireable characters
    return filter(lambda c: c not in removestring, sourcestring)


################################################################################
def prepOutput(cellOutput, cell, cell_index, output_index, imagedir, infile):

  captionStr = getMetaDataString(cell, 0, 'listingCaption', 'outputCaption','')
  labelStr = getMetaDataString(cell, 0, 'listingCaption', 'label','')
  if captionStr:
    captionStr = '{'+r'{} \label{{{}-out}}'.format(captionStr, labelStr)+'}'

  outstr = ''
  if 'text' in cellOutput.keys():
    outstr += encapsulateListing(cellOutput['text'], captionStr)
  elif 'data' in  cellOutput.keys():
    if 'text/html' in  cellOutput.data.keys():
      outs = cellOutput.data['text/html']
      outstr +=  processHTMLTree(outs,cell)
    if 'text/plain' in  cellOutput.data.keys():
      outstr += encapsulateListing(cellOutput.data['text/plain'], captionStr)    
  else:
    raise NotImplementedError("Unable to process cell {}, \nlooking for keys: {}".\
      format(cellOutput, cellOutput.keys()))

  return outstr

################################################################################
def encapsulateListing(outstr, captionStr):
  outstr = unicodedata.normalize('NFKD',outstr).encode('ascii','ignore')
  rtnStr = u'\n\\begin{lstlisting}'
  if captionStr:
    rtnStr += '[style=outcellstyle,caption={}]\n{}\n'.format(captionStr,outstr)
  else:
    rtnStr += '[style=outcellstyle]\n{}\n'.format(outstr)
  rtnStr += '\\end{lstlisting}\n\n'

  return rtnStr

################################################################################
def prepInput(cell, cell_index):
  rtnStr =''
  # v3 if 'input' in cell.keys():
  if 'source' in cell.keys():
    lines = cell.source.split('\n')
    if lines[0].startswith("#-- suppress"):
      if len(lines) > 1:
          if lines[1].startswith("#"):
              lsting = lines[1]
          else:
              return "\n\n"
    else:
      lsting = cell.source

    captionStr = getMetaDataString(cell, 0, 'listingCaption', 'caption','')
    labelStr = getMetaDataString(cell, 0, 'listingCaption', 'label','')
    if captionStr:
      captionStr = '{'+r'{} \label{{{}}}'.format(captionStr, labelStr)+'}'

    rtnStr = '\n\\begin{lstlisting}'
    if captionStr:
      rtnStr += '[style=incellstyle,caption={}]\n{}\n'.format(captionStr,lsting)
    else:
      rtnStr += '[style=incellstyle]\n{}\n'.format(lsting.encode('ascii','ignore'))
    rtnStr += '\\end{lstlisting}\n\n'

  return rtnStr

################################################################################
def prepExecuteResult(cellOutput, cell, cell_index, output_index, imagedir, infile):

  # if u'html' in cellOutput.keys() and 'table' in cellOutput[u'html']:
  #   return convertHtmlTable(cellOutput['html'],cell)

  if 'html' in cellOutput.keys():
      return processHTMLTree(cellOutput['html'],cell)

  if u'png' in cellOutput.keys():
      return processDisplayOutput(cellOutput, cell, cell_index, output_index, imagedir, infile)

  return prepOutput(cellOutput, cell, cell_index, output_index, imagedir, infile)



  # if 'text' in cellOutput.keys():
  #   outstr = cellOutput['text']
  # elif 'data' in  cellOutput.keys():
  #   if 'text/html' in  cellOutput.data.keys():
  #     doListing = False
  #     outstr = cellOutput.data['text/html']
  #     outstr = processHTMLTree(outstr,cell)
  #   if 'text/plain' in  cellOutput.data.keys():
  #     outstr = cellOutput.data['text/plain']
  # else:
  #   raise NotImplementedError("Unable to process cell {}, \nlooking for keys: {}".\
  #     format(cellOutput, cellOutput.keys()))



################################################################################
def prepError(cellOutput, cell, cell_index, output_index, imagedir, infile):
  import os, re 
  r= re.compile(r'\033\[[0-9;]+m') 
  rtnStr = '\n\\begin{verbatim}\n'
  for output in cell["outputs"]:
    # v3 if output['output_type'] == 'error':
    if output['output_type'] == 'error':
      for trace in output['traceback']:
        #convert to ascii and remove control chars
        rtnStr += re.sub(r'\033\[[0-9;]+m',"", trace.decode('ascii','ignore'))
  rtnStr += '\\end{verbatim}\n'
  return rtnStr

################################################################################
def prepNotYet(cellOutput, cell, cell_index, output_index, imagedir, infile):
  for output in cell["outputs"]:
    raise NotImplementedError("Unable to process cell type {}".\
                               format(output["output_type"]))

################################################################################
def extractBibtexXref(cell):

  #read the citation cross-reference map
  if 'bibxref' in cell['metadata'].keys():
    for key in cell['metadata']['bibxref'].keys():
      bibxref[key] = cell['metadata']['bibxref'][key]

  #read user-supplied bibtex entries.
  if 'bibtexentry' in cell['metadata'].keys():
    for key in cell['metadata']['bibtexentry'].keys():
      bibtexlist.append(cell['metadata']['bibtexentry'][key] + '\n\n')


################################################################################
def getMetaDataString(cell, output_index, captionID, metaID, defaultValue=''): 
  """process the metadata string, either a single string or a list of strings,
  and extract the string associated with output_index, if in a list
  """
  outStr = defaultValue 
  if captionID in cell['metadata'].keys():
    if metaID in cell['metadata'][captionID].keys():
      strIn = cell['metadata'][captionID][metaID].encode('ascii','ignore') #remove unicode
      if len(strIn):
        if strIn[0] is not '[':
          outStr = strIn
        else:
          stringlst = (eval(strIn))
          if output_index < len(stringlst):
            outStr = stringlst[output_index]
          else:
            outStr = defaultValue
  return outStr

################################################################################
def getMetaDataVal(cell, output_index, captionID, metaID, defaultValue=0): 
  """process the metadata string, either an int/float or a list of ints/floats,
  and extract the value associated with output_index, if in a list
  """
  outVal = defaultValue
  if captionID in cell['metadata'].keys():
    if metaID in cell['metadata'][captionID].keys():
      strIn = cell['metadata'][captionID][metaID]   
      if type(eval(strIn)) is not list:
        outVal = eval(strIn)
      else:
        lst = eval(strIn)
        if output_index < len(lst):
          outVal = lst[output_index]
        else:
          outVal = defaultValue
  return outVal
     
################################################################################
def processDisplayOutput(cellOutput, cell, cell_index, output_index, imagedir, infile):
  # print('********',cellOutput.keys())

  texStr = ''

  if 'name' in cellOutput.keys() :
    if cellOutput.name == 'stdout':
      if 'text' in cellOutput.keys() :
        return cellOutput.text

  if 'text/html' in cellOutput.keys() :
    return processHTMLTree(cellOutput['text/html'],cell)

  #handle png images
  pngCell = None
  #nbformat 4
  if 'data' in cellOutput.keys() and 'image/png' in cellOutput.data.keys():
    pngCell = cellOutput.data['image/png']
  #nbformat 3
  if 'png' in cellOutput.keys():
    pngCell = cellOutput.png
  if pngCell:
    imageName = infile.replace('.ipynb', '') + \
                '_{}_{}.png'.format(cell_index, output_index)
    with open(imagedir + '{}'.format(imageName), 'wb') as fpng:
      fpng.write(base64.decodestring(pngCell))

      #process the caption string, either a string or a list of strings
      captionStr = getMetaDataString(cell, output_index, 'figureCaption', 'caption','')
      labelStr = getMetaDataString(cell, output_index, 'figureCaption', 'label','')
      if labelStr:
        labelStr = '\\label{{{}-{}}}'.format(labelStr, output_index)

      #process the scale values, either a value or a list of value

      #build the complete bitmap size latex string    
      width = getMetaDataVal(cell, output_index, 'figureCaption', 'width', 0.0)
      scale = getMetaDataVal(cell, output_index, 'figureCaption', 'scale', 0.0)
      if width: # first priority
        sizeStr = '[width={}\\textwidth]'.format(width)
      elif scale: # second priority
        sizeStr = '[scale={}]'.format(scale) if scale else ''
      else: # none given, use assumed textwidth
        sizeStr = '[width=0.9\\textwidth]'

      if captionStr:
        texStr += '\n\\begin{figure}[tb]\n'
        texStr += '\\centering\n'
      else:
         texStr += '\\begin{center}\n'

      texStr += '\\includegraphics{}{{{}{}}}\n'.format(sizeStr,imagedir,imageName)

      if captionStr:
        texStr += '\\caption{'+'{}{}'.format(captionStr, labelStr) + '}\n'
        texStr += '\\end{figure}\n\n'
      else:
        texStr += '\\end{center}\n\n'

    return texStr

  if 'text/plain' in cellOutput.keys():
    return prepOutput(cellOutput, cell, cell_index, output_index, imagedir, infile)

  if 'data' in cellOutput.keys():
    if 'text/plain' in cellOutput.data.keys():
      return prepOutput(cellOutput, cell, cell_index, output_index, imagedir, infile)

  raise NotImplementedError("Unknow cell type(s): {}".format(cellOutput.keys()))

################################################################################
def convertRawCell(cell, cell_index, imagedir, infile):

  extractBibtexXref(cell)

  return cell['source']

################################################################################
def convertCodeCell(cell, cell_index, imagedir, infile):

  extractBibtexXref(cell)

  output = prepInput(cell, cell_index)
  for  count, cellOutput in enumerate(cell.outputs):
    #output += "<li>{}</li>".format(cellOutput.output_type)
    if cellOutput.output_type not in fnTableOutput:
      print(cellOutput.output_type)
      raise NotImplementedError("Unknown output type {}.".format(cellOutput.output_type))
    output += fnTableOutput[cellOutput.output_type](cellOutput, cell, cell_index, count, imagedir, infile)

  return output

################################################################################
def convertMarkdownCell(cell, cell_index, imagedir, infile):

  extractBibtexXref(cell)

  mkd = cell['source']

  # the problem is markdown will escape out slashes in the math environments
  # to try to fix this, let's find all the math environments
  # run markdown on them independently, to know what to search/replace for
  # this will probably break kind of badly for poorly formatted input,
  # particularly if $ and begin{eq..} are mixed within each other, but
  # hopefully you'll notice your input is broken in the notebook already?

  math_envs = []

  #the following block replaces $$ with begin/end {equation} sequences
  repstring = [r'\begin{equation}',r'\end{equation}']
  i = 0
  nlines = []
  ddollars = list(findAllStr(mkd, '$$'))
  if len(ddollars) > 0:
    lines = mkd.split('\n')
    for line in lines: 
      #ignore verbatim text
      if line[0:4] == '    ':
        nlines.append(line)
      else:
        #replace in sequence over one or more lines, one at a time
        while '$$' in line:
          line = line.replace('$$',repstring[i%2],1)
          i += 1
        nlines.append(line)
    #rebuild the markdown
    mkd = '\n'.join(nlines)

  dollars = list(findAllStr(mkd, '$'))
  ends = dollars[1::2]
  starts = dollars[::2]
  if len(starts) > len(ends):
    starts = starts[:-1]
  math_envs += [(s,e) for (s,e) in zip(starts, ends)]

  starts = list(findAllStr(mkd, '\n\\begin{equation}'))
  ends = [e + 13 for e in findAllStr(mkd, '\\end{equation}')]
  if len(starts) > len(ends):
    starts = starts[:-1]
  math_envs += [(s,e) for (s,e) in zip(starts, ends)]
  math_envs = sorted(math_envs)

  starts = list(findAllStr(mkd, '\n\\begin{equation*}'))
  ends = [e + 14 for e in findAllStr(mkd, '\\end{equation*}')]
  if len(starts) > len(ends):
    starts = starts[:-1]
  math_envs += [(s,e) for (s,e) in zip(starts, ends)]
  math_envs = sorted(math_envs)

  if math_envs:
    mkd_tmp = ""
    old_end = -1
    for start, end in math_envs:
      mkd_tmp += mkd[old_end+1:start]
      old_end = end
      cleaned =  mkd[start:end+1]
      for escapeable in '\\`*_{}[]()#+-.!':
        cleaned = cleaned.replace(escapeable, '\\' + escapeable)
      cleaned = cleaned.replace('\n', '')
      mkd_tmp += cleaned
    mkd = mkd_tmp + mkd[end+1:]

  html = markdown.markdown(mkd, extensions=['extra'])
  tmp = processHTMLTree(html,cell)

  # lines = tmp.split('\n')
  # for line in lines:
  #   if 'http' in line and r'\cite' in line:
  #     print(line)

  return unicode(tmp)

################################################################################
#process an html tree
def processHTMLTree(html,cell):
  table_index = 0
  tree = lxml.html.fromstring("<div>"+html+"</div>")
  tmp = ""
  for child in tree:
    # print('child.tag={}'.format(child.tag))
    # print('child.text={}'.format(child.text))
    # print('child.tail={}'.format(child.tail))

    if child.tag == 'h1' or (cell['cell_type']=="heading" and cell['level']==1):
      tmp += "\n\n\\chapter{" + child.text_content() + "}\n"
      seclabel = cleanFilename(child.text_content(),  removestring=" %:/,.\\[]=?~!@#$^&*()-_{};")
      tmp += r'\label{sec:' + seclabel + '}\n\n'

    elif child.tag == 'h2' or (cell['cell_type']=="heading" and cell['level']==2):
      tmp += "\n\n\\section{" + child.text_content() + "}\n"
      seclabel = cleanFilename(child.text_content(),  removestring=" %:/,.\\[]=?~!@#$^&*()-_{};")
      tmp += r'\label{sec:' + seclabel + '}\n\n'

    elif child.tag == 'h3' or (cell['cell_type']=="heading" and cell['level']==3):
      tmp += "\n\n\\subsection{" + child.text_content() + "}\n"
      seclabel = cleanFilename(child.text_content(),  removestring=" %:/,.\\[]=?~!@#$^&*()-_{};")
      tmp += r'\label{sec:' + seclabel + '}\n\n'

    elif child.tag == 'h4' or (cell['cell_type']=="heading" and cell['level']==4):
      tmp += "\n\n\\subsubsection{" + child.text_content() + "}\n"
      seclabel = cleanFilename(child.text_content(),  removestring=" %:/,.\\[]=?~!@#$^&*()-_{};")
      tmp += r'\label{sec:' + seclabel + '}\n\n'

    elif child.tag == 'h5' or (cell['cell_type']=="heading" and cell['level']==5):
      tmp += "\n\n\\paragraph{" + child.text_content() + "}\n"
      seclabel = cleanFilename(child.text_content(),  removestring=" %:/,.\\[]=?~!@#$^&*()-_{};")
      tmp += r'\label{sec:' + seclabel + '}\n\n'

    elif child.tag == 'h6' or (cell['cell_type']=="heading" and cell['level']==6):
      tmp += "\n\n\\subparagraph{" + child.text_content() + "}\n"
      seclabel = cleanFilename(child.text_content(),  removestring=" %:/,.\\[]=?~!@#$^&*()-_{};")
      tmp += r'\label{sec:' + seclabel + '}\n\n'

    elif child.tag == 'p' or child.tag == 'pre':
      tmp += processParagraph(child) + '\n'

    #this call may be recursive for nested lists
    elif child.tag == 'ul' or child.tag == 'ol':
      tmp += processList(child) + '\n'

    elif child.tag == 'blockquote':
      tmp += "\n\\begin{quote}\n" + processParagraph(child).strip() + "\\end{quote}\n\n"

    elif child.tag == 'table':
      tmp += convertHtmlTable(child, cell, table_index)
      table_index += 1

    elif child.tag == 'div':
      pass

    elif child.tag == 'iframe':
      pass

    elif child.tag == 'img':
      pass

    else:
      raise ValueError("Unable to process tag of type ", child.tag)

  # fix the lxml parser ignoring the \ for the latex envs
  #for env in ['equation']: # might want to extend this for other envs?
  #  tmp = tmp.replace('\nbegin{' + env + '}', '\n\\begin{' + env + '}')
  #  tmp = tmp.replace('\nend{' + env + '}', '\n\\end{' + env + '}')

  #first remove escaped \% if present, then do escape again on all % present
  tmp = tmp.replace('\\%','%')
  tmp = tmp.replace('%','\\%')

  # now do latex escapes - things markdown are fine with but latex isnt
  # in particular, underscore outside math env
  offset_count = 0
  for loc in findAllStr(tmp, '_'):
    # check for inline math
    loc += offset_count
    inline_count = sum([1 for i in findAllStr(tmp, '$') if i < loc])
    env_count = sum([1 for i in findAllStr(tmp, r'\begin{equation') if i < loc]) \
      + sum([1 for i in findAllStr(tmp, r'\end{equation') if i < loc])
    if (not inline_count % 2) and (not env_count % 2):
      tmp = tmp[:loc] + '\\' + tmp[loc:]
      offset_count += 1

  return tmp


################################################################################
def processList(lnode):
  envtype = 'itemize' if lnode.tag == 'ul' else 'enumerate'
  tmp = r"\begin{" + envtype + "}\n"
  for li in lnode:
    tmp += r"\item " + processParagraph(li).strip() + '\n'
  tmp += r"\end{" + envtype + "}\n"
  return tmp.strip() + '\n'


################################################################################
#dict to call processing functions according to cell type
fnTableCell = {
    'code' : convertCodeCell,
    'markdown' : convertMarkdownCell,
    'heading' : convertMarkdownCell,
    'raw' : convertRawCell,
    }

################################################################################
#dict to call processing functions according to cell output type
fnTableOutput = {
  'stream': prepOutput,
  'pyout': prepExecuteResult, # nbformat 3
  'execute_result': prepExecuteResult, # nbformat 4
  'display_data': processDisplayOutput,
  'pyerr': prepError, # nbformat 3
  'error': prepError, # nbformat 4
  'svg': prepNotYet,
  'png': prepNotYet,
  'application/pdf': prepNotYet,
  'text': prepNotYet,
   }


################################################################################
# create the picture directory
def createImageDir(imagedir):
  if imagedir is None:
    imagedir = './pic/'

  # print(imagedir, imagedir[-1])
  
  if imagedir[-1] is '\\' or imagedir[-1] is  '/':
    pass
  else:
    imagedir += '/'

  if not os.path.exists(imagedir):
      os.makedirs(imagedir)

  return imagedir

################################################################################
# here we do one at at time
def processOneIPynbFile(infile, outfile, imagedir):

  print('notebook={} latex={} imageDir={}'.format(infile,  outfile,  imagedir))
    
  pdffile = outfile.replace('.tex', '.pdf')
  bibfile = outfile.replace('.tex', '.bib')


  # nb = ipnbcurrent.read(io.open(infile, encoding='utf-8'), 'json')
  # if len(nb.worksheets) > 1:
    # raise NotImplementedError("Only one worksheet allowed")

  nb = nbformat.read(io.open(infile, encoding='utf-8'), nbformat.NO_CONVERT)
  output = '\n'

  # for cell_index, cell in enumerate(nb.worksheets[0].cells):
  if 'cells' not in nb:
    print("This notebook is probably not in Notebook 3 format.")
    if len(nb.worksheets) > 1:
      raise NotImplementedError("Only one worksheet allowed in Notebook 2 format.")
    nbcells = nb.worksheets[0].cells
  else:
    nbcells = nb.cells

  for cell_index, cell in enumerate(nbcells):
    # add a default header, if not otherwise supplied
    if cell_index==0:
      if cell.cell_type is not 'raw':
        output += standardHeader
      else:
        rtnString = fnTableCell[cell.cell_type](cell, cell_index, imagedir, infile)
    else:
      # print('\n********','cell.cell_type ={} cell={}'.format(cell.cell_type,cell))
      if cell.cell_type not in fnTableCell:
        raise NotImplementedError("Unknown cell type: >{}<.".format(cell.cell_type))
      rtnString = fnTableCell[cell.cell_type](cell, cell_index, imagedir, infile)
      output += rtnString

  if len(bibtexlist):
    output += '\n\n\\bibliographystyle{IEEEtran}\n'
    output += '\\bibliography{{{0}}}\n\n'.format(bibfile.replace('.bib', ''))

  output += r'\end{document}'+'\n\n'

  # #move the document class line to the start of the file
  # output = movedocumentclass(output)

  with io.open(outfile, 'w', encoding='utf-8') as f:
    f.write(unicode(output))

  if len(bibtexlist):
    with io.open(bibfile, 'w', encoding='utf-8') as f:
      for bib in bibtexlist:
        f.write(unicode(bib))



# ################################################################################
# def movedocumentclass(output):
#   """The file currently has the header up front, then the document class line.
#   We must move the document class line to the front of the file, ahead of the header.
#   """
#   lines = output.split('\n')
#   outlines = []
#   docclass = r'\documentclass[english]{workpackage}[1996/06/02]' #default value
#   for line in lines:
#     if '\\documentclass' in line:
#       docclass = line
#     else:
#       outlines.append(line)
#   #now we have the file without docclass and the stored docclass line, merge
#   outlines.insert(0, docclass)

#   return '\n'.join(outlines)

################################################################################
# here we get a list of all the input and outfiles
def getInfileNames(infile, outfile):

  infiles = []
  outfiles = []

  if infile is not None:
    if not infile.endswith(".ipynb"):
      raise ValueError("Invalid notebook filename {}.".format(infile))

    if outfile is None:
      outfile = infile.replace('.ipynb', '.tex')

    infiles.append(infile)    
    outfiles.append(outfile) 

  else: 
    # no input filename supplied, get all   
    ipynbfiles = listFiles('.', patterns='*.ipynb', recurse=0, return_folders=0)
    for ipynbfile in ipynbfiles:
      infiles.append(ipynbfile)    
      outfiles.append(ipynbfile.replace('.ipynb', '.tex')) 


  return infiles, outfiles


################################################################################
################################################################################
args = docopt.docopt(__doc__)

infile = args['<ipnbfilename>']
outfile = args['<outfilename>']
imagedir =  args['<imagedir>']

# find the image directory
imagedir = createImageDir(imagedir)

# see if only one input file, or perhaps many
infiles, outfiles = getInfileNames(infile, outfile)

#process the list of files found in spec
for infile, outfile in zip(infiles, outfiles):
  processOneIPynbFile(infile, outfile, imagedir)

print('\nfini!')
