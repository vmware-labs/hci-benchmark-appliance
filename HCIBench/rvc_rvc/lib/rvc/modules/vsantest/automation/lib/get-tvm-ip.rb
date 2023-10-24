#!/usr/bin/ruby
require_relative "rvc-util.rb"
require_relative "util.rb"

@tvm_folder_path_escape = _get_tvm_folder_path_escape[0]

`rvc #{$vc_rvc} --path #{@tvm_folder_path_escape} -c "vm.ip hci-tvm-*" \
-c 'exit' -q | awk '{print $NF}' > #{$tmp_path}/tvm.yaml`

`sed -i 's/$/"/g' #{$tmp_path}/tvm.yaml`
`sed -i 's/^/  - "/g' #{$tmp_path}/tvm.yaml`
`sed -i 's/\\("fe80:.*\\)\\("\\)$/\\1%eth1\\2/' #{$tmp_path}/tvm.yaml`
`sed -i '1i vms:\n' #{$tmp_path}/tvm.yaml`
`sed -i '1i ---\n' #{$tmp_path}/tvm.yaml`
