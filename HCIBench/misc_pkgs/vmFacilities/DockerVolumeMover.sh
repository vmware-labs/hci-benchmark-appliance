#!/bin/bash

#######################################################################################################
#Script Name	: DockerMover                                                                                             
#Description	: A script to move the docker files to a different location on the host.
#                 This script is especially codded and tested for moving docker files on HCIBench VMs.
#                 More info about HCIBench: https://labs.vmware.com/flings/hcibench                                                                                                                                                                    
#Authors       	: Xiaowei Chu (xiaoweic@vmware.com), Chen Wei (cwei@vmware.com)                                                                                      
#######################################################################################################

src='/var/lib/docker'
dst='/opt/output/results/DONT_TOUCH'
fflag=0

while getopts "fhs:d:" opt; do
  case ${opt} in
    f )
      fflag=1
      ;;
    h )
      echo Use the -s and -d flags to set the source and destination locations of docker containers. 
      echo Use the -f to suppress the interactions of the script.
      echo If no values are set, by default, this tool moves the docker containers from /var/lib/docker to /opt/output/results/DONT_TOUCH.
      exit
      ;;
    s )
      src="$OPTARG"
      ;;
    d )
      dst="$OPTARG"
      ;;
  esac
done


if [ "${dst: -1}" == "/" ] 
then
    dst="${dst::-1}"
fi

if [ "${src: -1}" == "/" ]
then
    src="${src::-1}"
fi

if [ -L $src ]
then
  echo "The source is a symbolic link. Please check if the docker containers have already been moved."
  exit
fi

if [ -d "${dst}/docker" ] || [ -L "${dst}/docker" ]
then
  echo "The destination dir has a subdir called 'docker'. To avoid unsafe overwriting, please move it to somewhere else or remove it before executing this script."
  exit
fi

if [ $fflag -eq 0 ]
then
    read -p "Are you sure to move the docker containers from ${src} to ${dst} ? (y/n): " yn
    case $yn in
        y ) ;;
        * ) 
            echo Exiting...
            exit;;
    esac
fi

echo Docker containers are being moved ... 

#Create the destination directory and set the permission
if [ ! -d "$dst" ]
then
  mkdir -p $dst
fi
chown root:root $dst && chmod 701 $dst

#Stop the running containers if any and the docker daemon.
exitNext=0
while true
do
  dockerstatus=$(systemctl is-active docker)
  #if docker is running, kill process and break out
  if [ "$dockerstatus" == "active" ]
  then
    containers=$(docker ps -q)
    if [ ${#containers} -ne 0 ]
    then
      docker stop $containers
    fi
    systemctl stop docker
    break
  #if not, check if docker is loading: 
  #if not loading, check process one more time, if not active then break out; 
  #if it's loading, wait for 3 secs and try again
  else
    if [ ${exitNext} == 1 ]
    then
      break
    fi
    systemctl list-jobs | grep docker
    isLoading=$?
    if [ ${isLoading} != 0 ]
    then
      exitNext=1
    fi
    sleep 3
  fi
done

#Reload the docker daemon config
systemctl daemon-reload

#Move the docker files to new location
mv ${src}/ ${dst}/

#Create the symbolic link
ln -s $dst/docker $src

#Start docker daemon
systemctl enable docker
systemctl start docker
echo Done!