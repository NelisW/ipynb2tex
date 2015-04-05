ipynb2tex
=========

Yet another IPython notebook to LaTeX converter - this one exports clean code in the user-required style, or can easily be absorbed in other reports.

The LaTeX converters supplied with IPython 2.x use Pygments to colour the Python code, as well as several other features which do not fit my requirement. 

##Features
  
-  Reads and converts IPython 2.x and 3.x files (nbformats 3 and 4).
-  Code is formatted as a LaTeX `lstlistings` environment, which looks neater to my eye.  
-  Pictures,  graphs and tables can be formatted as LaTeX floats, or in line with the text.  
-  Floating figures and tables can have LaTeX captions.  
-  Raw NBConvert cells are passed through to LaTeX with no change. 
-  References and hyperlinks are treated as first-class LaTeX references.  
-  HTML tables are reformatted as LaTeX tables.  
-  The header template interface allows the user to add his own style file.

##Deficiencies

   
1. Some complex cell-merged HTML tables may not render correctly in LaTeX (let me know if you have such a table).     
1. Unicode not yet handled.  
1. The following HTML elements are not currently processed, these elements are simply ignored: `div`, `iframe`, `img`.  
2. Many reserved LaTeX symbols such as hash, caret, underscore and dollar are 'legal' in normal markdown.  When rendering to LaTeX these symbols cause errors unless escaped with backslash.  In many cases these symbols are escaped, but not always because of context.  If the symbols are escaped, they render incorrectly in normal Markdown. Therefore, choose your target renderer and enter the symbols accordingly, accepting problems in the alternative renderer.
3. IPython notebook names must not have spaces in the filename.



##Instructions

The instructions on how to set up the notebook is given in the example notebook `test2LaTeX.ipynb`, please study it carefully. Someday when I have more time, I will write better instructions :-).

The most important (and most difficult) is to use the cell meta data to control LaTeX output such as:

- captions for figures, tables and listings.
- LaTeX citations and references.

See the example notebook for more information.

