# Aize-lang

## Getting Started
To use the programming language Aize, first download this repository onto your computer somehow.

### Requirements
* Python 3.7 exactly
    * No packages outside the standard library are needed
* A supported C Compiler somewhere on your computer
    * Clang or GCC on linux and on the path
    * MinGW on Windows, either through the path, in your user directory, or in Program Files
 
### Usage
Go to the `/aizelang` folder, wherever you put it.
Enter in the following command, assuming the correct Python is available on you path:
```commandline
python -m aizec test/fibo.aize --run
```
You should see the first 20 fibonacci numbers printed.
