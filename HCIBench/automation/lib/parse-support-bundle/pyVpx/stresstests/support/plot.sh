if [ $# != 1 ]
then
    echo Usage: $0 data_file
    exit 1
fi
cat << EOF
set xlabel 'Minutes Since Start Of Test'
set ylabel '# FDs or Handles / % CPU'
set y2label 'VM Size in MB / RSS in MB'
set terminal png medium size 1024,768
set output
set key below
set grid xtics ytics
set origin 0,0
plot '-' using 1:2  title 'VM Size' with lines linewidth 4, '' using 1:3 title 'VM RSS' with lines linewidth 4 , '' using  1:4 title '# FDs/Handles' with lines linewidth 4, '' using 1:5 title '% CPU' with lines linewidth 4
`cat $1`
e
`cat $1`
e
`cat $1`
e
`cat $1`
e
quit
