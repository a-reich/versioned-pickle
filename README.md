# versioned-pickle
A small utility Python package for adding environment metadata to pickle files and warning on mismatch when loaded.

# What does this do for me? 
`versioned-pickle` records metadata about the Python environment when used to pickle an object,
checks the new environment when unpickling, compares the two and warns if they are not considered to match.

If the pickle is completely unable to load, unpickling will still fails but you can check the metadata to determine which packages' versions
you should fix, and then hopefully reload successfully. In case of pickles that would load successfully but with results
that are silently incorrect or give wrong results when used with the different package versions, you **immediately**
see the warning indicating you may want to fix your versions, instead of assuming all is well and
encountering problems later when they are hard to debug or cause more damage.  
See [Background and Motivation](#background-and-motivation) for a full explanation. 
# What does this NOT do for me?
`versioned-pickle` will not "fix" your pickles from one environment so they can be used in a different one.

`versioned-pickle` will not handle the creation of a compatible environment for you - you will need to use the
outputted info to update your environment in whatever way you choose. This is because Python packaging is a complex
ecosystem and how to specify then recreate an environment has many nuances and several different tools
are popular (pip, conda, pipenv, poetry, etc.). 
# Installation
To install from source the latest commit from Github: `pip install git+https://github.com/a-reich/versioned-pickle.git`  
To install a specific built wheel from GH:  
` pip install versioned-pickle@https://github.com/a-reich/versioned-pickle/releases/download/v0.3.2/versioned_pickle-0.3.2-py3-none-any.whl`  
Python versions >=3.8 are supported.
# Usage
`versioned-pickle` provides a drop-in replacement for the standard library `pickle` module,
namely `dump/dumps` and `load/loads` functions. For example:
```
# with pandas==1.3.0 installed 
import pandas as pd, versioned_pickle as vpickle
myobj = pd.DataFrame({'x': range(10)})
with open('myobj.pkl', 'wb') as f:
	vpickle.dump(myobj, f)

# then, with pandas==1.3.4 installed
with open('myobj.pkl', 'rb') as f:
	newobj = vpickle.load(f)

# C:\Users\asafs\Desktop\Asaf\versioned_pickle\versioned_pickle\__init__.py:210: PackageMismatchWarning: Packages from pickling and unpickling environment do not match.
# Details of mismatched pickled, loaded versions:
# pandas: ('1.3.0', '1.3.4')
```
Three different methods ("scopes") are supported for determining which packages (or more properly, 'distributions')
to include, in increasing order of strictness:
* "object" (default) - the specific modules encountered when pickling the object
* "loaded" - any module that has currently been imported
* "installed" - all installed distributions.  

(The Python version is also recorded but not used in validation by default).
Environment metadata is obtained using `importlib.metadata`. Modules that are loaded directly
from sys.path without being installed as part of a distribution, or functions/classes
only defined in __main__, are ignored (it's assumed that if you're using this package you already
know not to do either). 

One feature of versioned-pickle is interoperability with regular pickle:
if for some reason your file is sent to someone who isn't aware of vpickle or doesn't want to use it,
they can still unpickle the file and will first get the metadata header, then on second read the desired object.

For more detailed documentation see the docstrings.

# Background and Motivation
The [pickle protocol](https://docs.python.org/3/library/pickle.html) is a powerful method provided by Python
for serializing and deserializing Python objects. It is popular since it is easy for users,
and supported on a very wide variety of complex or nested objects - it often "just works" for new custom types
from whatever libraries you're using and library authors can customize the process.

However, experts often raise problems with its use in various scenarios, including long-term storage
or sending pickles between different contexts/applications. One issue is that pickling can be sensitive to
changes in the code of the types being pickled. This is because pickle serializes the *data*
belonging to e.g. a class instance, but not the code defining the class behavior - when unpickled,
the class name is simply looked up and imported if necessary. Therefore, **any time some of the modules an object relies on
have different versions when unpickling than when pickled is a potential source of bugs**.

For example, this pandas [issue](https://github.com/pandas-dev/pandas/issues/34535) reported that
pandas DataFrames created with pandas 0.25 failed on loading with pandas 1.0.3. (Note that pickle compatibility is a stronger requirement than normal forward compatibility -
 even if a library declares it guarantees Semantic Versioning, this does not guarantee the former.) 
**This is the problem versioned-pickle aims to help with.**

There are two sorts of issues that can be caused by packages' pickle incompatibility:
### 1. Unpickling failures
Unpickling fails outright with different versions, i.e. raises an exception. This scenario
is difficult to recover from after the fact, but it is clear that something went wrong.
### 2. Unpickling gives silently incorrect results 
Unpickling itself may execute but give objects whose data is invalid or gives incorrect results in
the new environment.  
For example, suppose we have a class `Employee` which stores info about employees
including an integer attribute `salary_last_year`. Later, we decided that some employees
earned sales commissions which were included in the number but it's more useful to separate that
into a new field `commisssion_last_year` with default 0 and make `salary` only the regular salary.  
If we used the old version to pickle an employee with 50,000 regular salary and 20,000 commission, their
`salary_last_year` would be 70K. On unpickling with the new version the instance would have
`salary_last_year` of 70K and no commission, which would be wrong under the current code's interpretation. 
These issues are common in e.g. data analytics & machine learning uses, where complex models or
arbitrary transformation pipelines may need to be stored as pickles after training but can give
wrong numerical results - that aren't immediately obvious - if the exact assumptions and representation of
the model changes.

In some scenarios there are good reasons to use a more robust serialization process, e.g. one specific
to the type of data at hand, but sometimes pickle is the best feasible option and in that case
versioned-pickle helps control the compatibility risks. It helps in both scenarios above,
but especially avoids the costs of #2.
