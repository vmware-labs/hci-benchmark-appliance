# Copyright (c) 2011 VMware, Inc.  All Rights Reserved.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

require 'rvc/connection'

require 'rbvmomi'
VIM = RbVmomi::VIM
VIM.add_extension_dir File.join(File.dirname(__FILE__), "extensions")

class RbVmomi::VIM
  include RVC::Connection

  def children
    rootFolder.children
  end

  def display_info
    puts serviceContent.about.fullName
  end

  # In Standalone vSAN Mgmt Mode, there is Non-VC but Vsan Mgmt service act
  # as VC, all of the available commands will work as normal VC mode and
  # some inapplicable commands will be disabled.
  # However, it's transparent to vSAN users(through RVC)
  def vsan_standalone_mode
    serviceContent.about.apiType == 'VsanMgmt'
  end
end
