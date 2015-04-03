ipynb2tex
=========
<font color="red">This script reads __only__ IPython  3.x files (nbformat 4).</font>

Yet another IPython notebook to LaTeX converter - this one exports clean code in the user-required style, or can easily be absorbed in other reports.

The LaTeX converters supplied with IPython 2.x use Pygments to colour the Python code, as well as several other features which do not fit my requirement. Features of this converter are: 
  
-  Code is formatted as a LaTeX lstlistings environment, which looks neater to my eye.  
-  Pictures,  graphs and tables can be formatted as LaTeX floats, or in line with the text.  
-  Floating figures and tables can have LaTeX captions.  
-  Raw NBConvert cells are passed through to LaTeX with no change. 
-  References and hyperlinks are treated as first-class LaTeX references.  
-  HTML tables are reformatted as LaTeX tables.  
-  The header template interface allows the user to add his own style file.

##Deficiencies

- Mathematics enclosed in two dollar signs do not always render correctly, also affecting subsequent math rendering.   
-  A config file is required to better define in one place the variables such as the path to the images, etc.   
- Multiple output listings may arise if the output is written by different cells (see the example above).   
-  Some complex cell-merged HTML tables may not render correctly in LaTeX (let me know if you find a bughave such a table).    
- Unicode not yet handled.

##Instructions

The instructions on how to set up the notebook is given in the example notebook `test2LaTeX.ipynb', please study it carefully. Someday when I have more time, I will write better instructions :-).

The most important (and most difficult) is to use the cell meta data to control LaTeX output such as:

- captions for figures, tables and listings.
- LaTeX citations and references.

See the example notebook for more information.

