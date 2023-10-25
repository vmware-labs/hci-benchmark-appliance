# HCIBench

## Overview
HCIBench stands for "Hyper-converged Infrastructure Benchmark". It's essentially an automation wrapper around the popular and proven open source benchmark tools: Vdbench and Fio that make it easier to automate testing across a HCI cluster. HCIBench aims to simplify and accelerate customer POC performance testing in a consistent and controlled way. The tool fully automates the end-to-end process of deploying test VMs, coordinating workload runs, aggregating test results, performance analysis and collecting necessary data for troubleshooting purposes.

HCIBench is not only a benchmark tool designed for vSAN, but also could be used to evaluate the performance of all kinds of Hyper-Converged Infrastructure Storage in vSphere environment.

## Try it out

### Prerequisites

* Web Browser: IE8+, Firefox or Chrome
* vSphere 6.5 and later environments for both HCIBench and its client VMs deployment
* Before deploying HCIBench the environment must meet the following requirements:
  - The cluster is created and configured properly
  - The vSphere environment where the tool is deployed can access the vSAN Cluster environment to be tested
  - The network that will be used by the Guest VM is defined on all the hosts in the cluster. If a DHCP service is available, the Guest VM can obtain their network configurations from the DHCP server. If the network does not have DHCP service or an insufficient number of IP addresses
HCIBench can assign static IP address.

### Deploy

You can choose to deploy HCIBench appliance OVA to vSphere environment if there's no existing HCIBench instance running in your environment 

1. Download HCIBench OVA from https://github.com/vsphere-tmm/HCIBench/releases
2. Deploy HCIBench OVA into your vSphere environment. Refer to [HCIBench User Guide](HCIBench_User_Guide_2.8.1.pdf) for more details
3. Configure the HCIBench testing and start testing

### Upgrade
You can choose to upgrade HCIBench with the latest code if there is existing HCIBench instance running in your environment 

#### Prerequisites
*  You need to have HCIBench Controller VM running
*  Your HCIBench VM should have internet connectivity

#### Steps
1. SSH into your HCIBench VM and run the following cmds to upgrade your HCIBench to the latest build
2. tdnf install -y git && git clone https://github.com/vmware-labs/hci-benchmark-appliance.git && sh hci-benchmark-applianc/HCIBench/upgrade.sh

or you can get the zip file
cd /root/ && wget https://github.com/vmware-labs/hci-benchmark-appliance/archive/refs/heads/main.zip && unzip master && sh /root/HCIBench-master/HCIBench/upgrade.sh

Then the logs, results and configuration files will be preserved after upgrading to the latest build.

## Documentation
[HCIBench User Guide](HCIBench_User_Guide_2.8.1.pdf)

## Contributing

The hci-benchmark-appliance project team welcomes contributions from the community. Before you start working with hci-benchmark-appliance, please
read our [Developer Certificate of Origin](https://cla.vmware.com/dco). All contributions to this repository must be
signed as described on that page. Your signature certifies that you wrote the patch or have the right to pass it on
as an open-source patch. For more detailed information, refer to [CONTRIBUTING.md](CONTRIBUTING.md).

## License

HCI Benchmark Appliance
Copyright 2023 VMware, Inc.

The MIT license (the "License") set forth below applies to all parts of the HCI Benchmark Appliance project. You may not use this file except in compliance with the License.

MIT License

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do
so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

## Notice

HCI Benchmark Appliance
Copyright 2023 VMware, Inc. 

This product is licensed to you under the MIT license (the "License"). You may not use this product except in compliance with the MIT License.  

This product may include a number of subcomponents with separate copyright notices and license terms. Your use of these subcomponents is subject to the terms and conditions of the subcomponent's license, as noted in the LICENSE file. 



