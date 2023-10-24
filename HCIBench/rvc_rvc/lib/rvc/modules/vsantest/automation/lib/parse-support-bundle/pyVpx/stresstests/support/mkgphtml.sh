if ! [ -f "$1" ]
then
   echo Usage: $0 data_file
   exit 1
fi
tail +2 "$1" | tr -d '"' | awk -F\, '{print NR*0.5, $2/(1024*1024), $3/(1024*1024), $4, $5}' > "$1".tmp
export LD_LIBRARY_PATH=~msharma/gnuplot-4.0.0/lib:$LD_LIBRARY_PATH
export PATH=~msharma/gnuplot-4.0.0/bin:$PATH
./plot.sh "$1".tmp | gnuplot > "$1".png
echo '<html><body><img src="'`basename "$1"`'.png"/></body></html>' > "$1".html
rm "$1".tmp
