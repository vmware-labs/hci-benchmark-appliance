__all__ = [ "vim" ]

# Put in initialization list
for name in __all__:
   __import__(name, globals(), locals(), [], 1)
