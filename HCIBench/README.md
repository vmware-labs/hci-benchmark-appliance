# HCIBench
I have this repo maintained is for user to upgrade their HCIBench instance without deploying another OVA.
To upgrade your HCIBench:
  1. You need to have HCIBench Controller VM running
  2. Your HCIBench Controller VM should have internet connectivity
  3. SSH into your HCIBench Controller VM and run the following cmds to upgrade your HCIBench to the latest build
 
  tdnf install -y git && git clone https://github.com/cwei44/HCIBench.git && sh HCIBench/upgrade.sh
  
  or

  cd /root/ && wget https://codeload.github.com/cwei44/HCIBench/zip/master && unzip master && sh /root/HCIBench-master/upgrade.sh
  
  4. the logs, results and configuration files will be preserved after upgrading to the latest build.
