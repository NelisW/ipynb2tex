ipynb2tex
=========
This script reads IPython 3.x files (nbformat 4).
There is still a warning on a deprecated function call which will be attended to in due time.

Yet another IPython notebook to LaTeX converter - this one exports clean code easily absorbed in other reports.

The LaTeX converters supplied with IPython use Pygments to colour the Python code, as well as several other features which are not in my standard toolkit. Features of this converter are: 
  
-  Code is formatted as a LaTeX lstlistings environment, which looks neater to my eye.  
-  Pictures and graphs are formatted as floats, not in line with the text.  
-  Tables are formatted as floats. 
-  Floating figures and tables can have captions.  
-  Raw NBConvert cells are passed through to LaTeX with no change. 
-  References and hyperlinks are treated as first-class LaTeX references.  
-  HTML tables are reformatted as LaTeX tables (complex merged rows and columns might not always work as expected).  

The known deficiencies are:  

- Mathematics enclosed in two dollar signs do not always render correctly, also affecting subsequent math rendering.  
- The header template interface is very limited at moment; just a single file that is included as a single entity.
-  A config file is required to better define in one place the variables such as the path to the images, etc.
- Multiple output listings may arise if the output is written by different cells (see the example above).

##Instructions


The instructions on how to set up the notebook is given in the example notebook `test2LaTeX.ipynb', please study it carefully. Someday when I have more time, I will write better instructions :-).

The most important (and most difficult) is to use the cell meta data to control LaTeX output such as:

- captions for figures, tables and listings.
- LaTeX citations and references.

See the example notebook for more information.

