#!/usr/bin/python
# Copyright 2007 VMware, Inc.  All rights reserved. -- VMware Confidential
## A command line interface widget used to build a text based list view.

(JUSTIFY_LEFT,
 JUSTIFY_CENTER,
 JUSTIFY_RIGHT) = range(3)

## Utility class to print a text cell in a table
#
# A cell may only occupy one row of text.
class CellPrinter:
   ## Constructor
   #
   # @param  minWidth [in] minimum width the cell should occupy.
   # @param  maxWidth [in] maximum width the cell should occupy.
   def __init__(self, minWidth=0, maxWidth=-1):
      self.prefix = ''
      self.minWidth = minWidth
      self.maxWidth = maxWidth
      self.filler = ' '
      self.justify = JUSTIFY_LEFT
      

   ## Produce cell text.
   #
   # @param  val [in] unformatted cell text to format in cell.
   # @return the formatted cell text.
   def Print(self, val):
      s = ''

      fieldWidth = len(val)
      if self.minWidth > fieldWidth:
         fieldWidth = self.minWidth
      if self.maxWidth > -1 and fieldWidth > self.maxWidth:
         fieldWidth = self.maxWidth

      numFiller = fieldWidth - len(val)

      s += self.prefix

      # If left justified, print string before spacing
      if numFiller > 0:
         numPrint = 0
         if self.justify == JUSTIFY_RIGHT:
            numPrint = numFiller
         elif self.justify == JUSTIFY_CENTER:
            numPrint = (numFiller / 2)

         s += self.filler * numPrint
         numFiller -= numPrint

      if fieldWidth < len(val):
         s += val[:fieldWidth]
      else:
         s += val

      # Print remaining characters to the end of the cell
      if numFiller > 0:
         s += self.filler * numFiller

      return s
      
   ## Prints a debug string describing the CellPrinter.
   #
   # @return debug string.
   def ToString(self):
      return "CellPrinter" + str(self.__dict__)


## Class that describes properties of a column
class ColumnProperties:
   def __init__(self, name, visible=True, maxWidth=-1, justify=JUSTIFY_LEFT):
      self.name = name
      self.visible = visible
      self.maxWidth = maxWidth
      self.justify = justify


## Utility class to print and format a text list view.
class ListView:
   # Constructor
   def __init__(self, table):
      # Cell padding
      self._cellPadding = 2
      # Should column heading be shown?
      self._showColumnHeading = True
      # How many characters to indent the whole ListView
      self._indent = 0
      # Next identifier for item
      self._nextItemId = 0
      # Table over which ListView will be created
      self._table = table

      # Settable properties of a column
      self._columnProperties = {}

      # Initialize properties for a column
      columnNames = table.GetColumnNames()
      for columnName in columnNames:
         self._columnProperties[columnName] = ColumnProperties(columnName)

   ## Gets additional whitespace between cells.
   #
   # Gets the amount of additional whitespace that should be placed between
   # cells.  The space does not include the cell delimiter.
   #
   # @return number of spaces to place between cells.
   def GetCellPadding(self):
      return self._cellPadding

   ## Sets additional whitespace between cells.
   #
   # Sets the amount of additional whitespace that should be placed between
   # cells.  The space does not include the cell delimiter.
   #
   # @param  padding [in] number of spaces to place between cells.
   def SetCellPadding(self, padding):
      self._cellPadding = padding

   ## Gets whitespace to indent entire list view.
   #
   # Gets the amount of whitespace to indent the list view.  The entire list
   # view table is moved by this amount of space.
   #
   # @return number of spaces to indent list view.
   def GetIndent(self):
      return self._indent

   ## Sets whitespace to indent entire list view.
   #
   # Sets the amount of whitespace to indent the list view.  The entire list
   # view table is moved by this amount of space.
   #
   # @param  indent [in] number of spaces to indent list view.
   def SetIndent(self, indent):
      self._indent = indent

   ## Gets whether the cell column heading will be shown.
   #
   # @return  whether cell column heading will be shown.
   def GetShowHeading(self):
      return self._showColumnHeading

   ## Sets whether the cell column heading will be shown.
   #
   # @param  showColumnHeading [in] whether cell column heading will be shown.
   def SetShowHeading(self, showColumnHeading):
      self._showColumnHeading = showColumnHeading

   ## Gets the visibility of a named column.
   #
   # @param  column [in] column name.
   # @return visibility for column.
   def GetColumnVisible(self, column):
      columnProperties = self.GetColumnProperties(column)
      return self._columnProperties[column].visible

   ## Sets the visibility of a named column.
   #
   # @param  column [in] column name.
   # @param  visible [in] visibility for column.
   def SetColumnVisible(self, column, visible):
      columnProperties = self.GetColumnProperties(column)
      columnProperties.visible = visible

   ## Gets the maximum width of a named column.
   #
   # @param  column [in] column name.
   # @return maximum width for column.
   def GetColumnMaxWidth(self, column):
      columnProperties = self.GetColumnProperties(column)
      return self._columnProperties[column].maxWidth

   ## Sets the maximum width of a named column.
   #
   # @param  column [in] column name.
   # @param  maxWidth [in] maximum width for column.
   def SetColumnMaxWidth(self, column, maxWidth):
      columnProperties = self.GetColumnProperties(column)
      columnProperties.maxWidth = maxWidth

   ## Gets the text justification for a named column.
   #
   # @param  column [in] column name.
   # @return text justification.
   def GetColumnJustify(self, column):
      columnProperties = self.GetColumnProperties(column)
      return columnProperties.justify

   ## Sets the text justification for a named column.
   #
   # @param  column [in] column name.
   # @param  justify [in] text justification.
   def SetColumnJustify(self, column, justify):
      columnProperties = self.GetColumnProperties(column)
      columnProperties.justify = justify

   ## Add a category to use to group list view items.
   #
   # The category must refer to a defined column.
   #
   # @param  column [in] column name.
   #
   # @todo implement category printing for the ListView.  These are currently
   #       ignored.
   def AddCategory(self, column):
      pass

   ## Clear categories to use to group list view items.
   def ClearCategory(self):
      pass

   ## Produces a CSV string version of the ListView.
   #
   # @return CSV string.
   def ToCsvString(self):
      # Build simple CellPrinters for each column
      table = self._table
      rowIds = table.GetRowIds()     
      columnNames = table.GetColumnNames()
      numColumns = len(columnNames)

      printers = map(lambda x: CellPrinter(), range(numColumns))
      return self.ToStringInt(',', False, printers, printers, rowIds, columnNames, table);

   ## Produces a string of the ListView according to format policies.
   #
   # @return formatted ListView string.
   def ToString(self):
      table = self._table
      rowIds = table.GetRowIds()     
      columnNames = table.GetColumnNames()
      numColumns = len(columnNames)

      # Determine maximum widths for each field
      if self._showColumnHeading:
         maxWidths = [len(x) for x in columnNames]
      else:
         maxWidths = [0 for x in columnNames]

      for row in rowIds:
         for col in range(numColumns):
            columnName = columnNames[col]
            value = table.Get(row, columnName)
            if len(value) > maxWidths[col]:
               maxWidths[col] = len(value)

      # Enforce the maximum width set by the definition of the column
      for col in range(numColumns):
         defMaxWidth = self.GetColumnMaxWidth(columnNames[col])
         if defMaxWidth > -1 and maxWidths[col] > defMaxWidth:
            maxWidths[col] = defMaxWidth

      #
      # Build CellPrinters for each column
      #
      # Categories affect the indenting.  Handle them when categories are implemented.
      #
      
      printers = []
      headPrinters = []
      for col in range(numColumns):
         minWidth = maxWidths[col];
         maxWidth = maxWidths[col];

         padding = ''
         if col == 0 and self._indent > 0:
            padding = self._indent * ' '
         elif col > 0:
            cellPadding = self.GetCellPadding()
            if cellPadding > 1:
               padding = cellPadding * ' '

         columnName = columnNames[col]
         justify = self.GetColumnJustify(columnName)

         # Build list view data CellPrinters.
         printer = CellPrinter(minWidth, maxWidth)
         printer.prefix = padding;
         printer.justify = justify;
         printers.append(printer);

         # Build separate CellPrinters for the category headers printers.
         headPrinter = CellPrinter(minWidth, maxWidth)
         headPrinter.prefix = padding;
         headPrinter.justify = JUSTIFY_CENTER;
         headPrinters.append(headPrinter);

      return self.ToStringInt(' ', True, headPrinters, printers, rowIds, columnNames, table);

   ## Internal utility function to produce ListView string.
   # 
   # @param  columnDelimiter [in] delimiter to separate columns.
   # @param  showCategories [in] should rows be grouped into categories.
   # @param  headPrinters [in] CellPrinters to print the column headers.
   # @param  printers [in] CellPrinters to print the item data.
   # @param  rows [in] items to print.
   def ToStringInt(self, columnDelimiter, showCategories, allHeadPrinters,
                   allPrinters, rowIds, allColumnNames, table):
      allNumColumns = len(allColumnNames)

      # Filter down printers and columns to just those that are visible
      visibleColumnIdxs = filter(
         lambda col: self.GetColumnVisible(allColumnNames[col]),
         xrange(allNumColumns))
      columnNames = map(lambda x: allColumnNames[x], visibleColumnIdxs)
      numColumns = len(columnNames)
      printers = map(lambda x: allPrinters[x], visibleColumnIdxs)
      headPrinters = map(lambda x: allHeadPrinters[x], visibleColumnIdxs)

      rowStrings = []

      if self._showColumnHeading:
         # Display Column Headers
         colStrings = map(lambda col: headPrinters[col].Print(columnNames[col]),
                          xrange(numColumns))
         rowStrings.append(columnDelimiter.join(colStrings))
   
      # Consider categories
   
      for row in rowIds:
         # Display Column Data
         columnData = map(lambda columnName: table.Get(row, columnName),
                          columnNames)
         colStrings = map(lambda col: printers[col].Print(columnData[col]),
                          xrange(numColumns))
         rowStrings.append(columnDelimiter.join(colStrings))
   
      return str("\n").join(rowStrings)

   ## Converts from column name to column identifier.
   # 
   # @param  column [in] column name.
   # @return column identifier.
   def GetColumnProperties(self, column):
      return self._columnProperties[column]


def main():
   pass

if __name__ == "__main__":
    main()
