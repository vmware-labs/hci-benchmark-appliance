#!/usr/bin/ruby
require 'ipaddr'
require 'nokogiri'
require 'shellwords'

hash={}
doc = Nokogiri::XML(File.open("/root/tmp/ovfEnv.xml"))

doc.xpath('//xmlns:Property').map do |pp|
  hash[pp.attributes["key"].value] = pp.attributes["value"].value
end

ip_version = hash["IP_Version"]
dns = hash["DNS"]

if hash["Public_Network_Type"] == "Static"
  ip = hash["Public_Network_IP"]
  netsize = hash["Public_Network_Size"]
  gw = hash["Public_Network_Gateway"]
  `sed -i "s/^DHCP=.*$/DHCP=no/g" /etc/systemd/network/eth0.network`
  `echo "Address=#{ip}/#{netsize}" >> /etc/systemd/network/eth0.network`
  `echo "Gateway=#{gw}" >> /etc/systemd/network/eth0.network`
  `echo "DNS=#{dns}" >> /etc/systemd/network/eth0.network`
  `echo "net.ipv6.conf.eth0.autoconf = 0" > /etc/sysctl.d/ipv6_eth0_autoconf.conf; sysctl -p --load /etc/sysctl.d/ipv6_eth0_autoconf.conf` if ip_version == "IPV6"
elsif hash["Public_Network_Type"] == "DHCP"
  `sed -i "s/^DHCP=.*$/DHCP=#{ip_version.downcase}/g" /etc/systemd/network/eth0.network`
  `echo "net.ipv6.conf.eth0.autoconf = 0" > /etc/sysctl.d/ipv6_eth0_autoconf.conf; sysctl -p --load /etc/sysctl.d/ipv6_eth0_autoconf.conf` if ip_version == "IPV6"
else #autoconf
  `echo "net.ipv6.conf.eth0.autoconf = 1" > /etc/sysctl.d/ipv6_eth0_autoconf.conf; sysctl -p --load /etc/sysctl.d/ipv6_eth0_autoconf.conf` if ip_version == "IPV6"
end
`echo "DNS=#{dns}" >> /etc/systemd/network/eth0.network` if dns != ""
`systemctl restart systemd-networkd`

password = hash["System_Password"]
psd = Shellwords.escape("root:#{password}")
psd_escape = Shellwords.escape(password)
system(%{echo #{psd} | chpasswd})
tomcat = `/var/opt/apache-tomcat-8.5.68/bin/digest.sh -a md5 -h org.apache.catalina.realm.MessageDigestCredentialHandler '#{psd_escape}'`
tomcat_psd = tomcat.chomp.rpartition(":").last
`echo '<?xml version="1.0" encoding="UTF-8"?>' > /var/opt/apache-tomcat-8.5.68/conf/tomcat-users.xml`
`echo '<tomcat-users xmlns="http://tomcat.apache.org/xml" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://tomcat.apache.org/xml tomcat-users.xsd" version="1.0">' >> /var/opt/apache-tomcat-8.5.68/conf/tomcat-users.xml`
`echo '<role rolename="root"/>' >> /var/opt/apache-tomcat-8.5.68/conf/tomcat-users.xml`
`echo '<user username="root" password="#{tomcat_psd}" roles="root"/>' >> /var/opt/apache-tomcat-8.5.68/conf/tomcat-users.xml`
`echo '</tomcat-users>' >> /var/opt/apache-tomcat-8.5.68/conf/tomcat-users.xml`
`service tomcat stop; sleep 2; service tomcat start`
