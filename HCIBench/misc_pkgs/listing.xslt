<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet xmlns:xsl="http://www.w3.org/1999/XSL/Transform" version="1.0">

  <xsl:output method="html" encoding="UTF-8" indent="yes"
              doctype-public="-//W3C//DTD HTML 4.01//EN"
              doctype-system="http://www.w3.org/TR/html4/strict.dtd"/>

  <!-- Recursively extracts the last path segment from a path that does NOT end in / -->
  <xsl:template name="basename">
    <xsl:param name="path"/>
    <xsl:choose>
      <xsl:when test="contains($path, '/')">
        <xsl:call-template name="basename">
          <xsl:with-param name="path" select="substring-after($path, '/')"/>
        </xsl:call-template>
      </xsl:when>
      <xsl:otherwise><xsl:value-of select="$path"/></xsl:otherwise>
    </xsl:choose>
  </xsl:template>

  <xsl:template match="listing">
    <xsl:variable name="path">
      <xsl:value-of select="@contextPath"/>
      <xsl:if test="@directory != '/'">/<xsl:value-of select="@directory"/></xsl:if>
    </xsl:variable>

    <html>
      <head>
        <meta http-equiv="Content-Type" content="text/html; charset=UTF-8"/>
        <title>Index of <xsl:value-of select="$path"/></title>
        <style>
          * { box-sizing: border-box; margin: 0; padding: 0; }

          body {
            font-family: Consolas, "Liberation Mono", "Courier New", monospace;
            font-size: 13px;
            background-color: #1b2a32;
            color: #acbac3;
            padding: 20px 24px;
          }

          h1 {
            font-size: 16px;
            font-weight: 600;
            color: #e8f1f5;
            margin-bottom: 16px;
            padding-bottom: 10px;
            border-bottom: 1px solid #2d4150;
          }

          table {
            width: 100%;
            border-collapse: collapse;
          }

          thead tr {
            background-color: #0f1e26;
          }

          thead th {
            text-align: left;
            padding: 6px 10px;
            color: #e8f1f5;
            font-weight: 600;
            border-bottom: 2px solid #2d4150;
            white-space: nowrap;
          }

          thead th.col-size  { text-align: right; width: 80px; }
          thead th.col-date  { width: 160px; }
          thead th.col-icon  { width: 28px; padding-right: 0; }
          thead th.col-name  { }

          thead th a {
            color: #e8f1f5;
            text-decoration: none;
          }
          thead th a:hover { text-decoration: underline; }

          tbody tr:hover { background-color: #223040; }

          tbody tr.alt { background-color: #172229; }

          td {
            padding: 4px 10px;
            border-bottom: 1px solid #1e2f3a;
            vertical-align: middle;
            white-space: nowrap;
          }

          td.col-icon {
            padding-right: 2px;
            color: #6a8799;
            font-size: 12px;
          }

          td.col-name a {
            color: #4aaed9;
            text-decoration: none;
          }
          td.col-name a:hover { text-decoration: underline; }

          td.col-date { color: #8aa4b5; }

          td.col-size {
            text-align: right;
            color: #8aa4b5;
          }

          tr.parent-row td.col-icon { color: #6a8799; }
          tr.parent-row td.col-name a { color: #4aaed9; }

          hr.top, hr.bottom {
            border: none;
            border-top: 1px solid #2d4150;
            margin: 12px 0;
          }

          .address {
            margin-top: 14px;
            color: #4a6070;
            font-size: 11px;
          }
        </style>
      </head>
      <body>
        <h1>Index of <xsl:value-of select="$path"/></h1>
        <hr class="top"/>
        <table>
          <thead>
            <tr>
              <th class="col-icon"/>
              <th class="col-name">
                <a href="?C=N;O=A">Name</a>
              </th>
              <th class="col-date">
                <a href="?C=M;O=A">Last Modified</a>
              </th>
              <th class="col-size">
                <a href="?C=S;O=A">Size</a>
              </th>
            </tr>
          </thead>
          <tbody>
            <!-- Parent directory row -->
            <xsl:if test="@hasParent = 'true'">
              <tr class="parent-row">
                <td class="col-icon">[..]</td>
                <td class="col-name"><a href="../">Parent Directory</a></td>
                <td class="col-date">&#160;</td>
                <td class="col-size">-</td>
              </tr>
            </xsl:if>

            <!-- Directories first -->
            <xsl:for-each select="entries/entry[@type='dir' and not(contains(@urlPath, '.DONT_TOUCH'))]">
              <xsl:sort select="@urlPath" order="ascending"/>
              <!-- strip trailing slash, get last segment, re-add slash -->
              <xsl:variable name="stripped" select="substring(@urlPath, 1, string-length(@urlPath) - 1)"/>
              <xsl:variable name="name">
                <xsl:call-template name="basename">
                  <xsl:with-param name="path" select="$stripped"/>
                </xsl:call-template>
                <xsl:text>/</xsl:text>
              </xsl:variable>
              <tr>
                <xsl:if test="position() mod 2 = 0">
                  <xsl:attribute name="class">alt</xsl:attribute>
                </xsl:if>
                <td class="col-icon">[DIR]</td>
                <td class="col-name">
                  <a href="{@urlPath}"><xsl:value-of select="$name"/></a>
                </td>
                <td class="col-date"><xsl:value-of select="@date"/></td>
                <td class="col-size">-</td>
              </tr>
            </xsl:for-each>

            <!-- Files -->
            <xsl:for-each select="entries/entry[@type='file']">
              <xsl:sort select="@urlPath" order="ascending"/>
              <xsl:variable name="name">
                <xsl:call-template name="basename">
                  <xsl:with-param name="path" select="@urlPath"/>
                </xsl:call-template>
              </xsl:variable>
              <tr>
                <xsl:if test="position() mod 2 = 0">
                  <xsl:attribute name="class">alt</xsl:attribute>
                </xsl:if>
                <td class="col-icon">
                  <xsl:choose>
                    <xsl:when test="substring($name, string-length($name) - 2) = '.gz'">[GZ ]</xsl:when>
                    <xsl:when test="substring($name, string-length($name) - 3) = '.zip'">[ZIP]</xsl:when>
                    <xsl:when test="substring($name, string-length($name) - 3) = '.log'">[LOG]</xsl:when>
                    <xsl:when test="substring($name, string-length($name) - 3) = '.csv'">[CSV]</xsl:when>
                    <xsl:when test="substring($name, string-length($name) - 3) = '.txt'">[TXT]</xsl:when>
                    <xsl:when test="substring($name, string-length($name) - 3) = '.pdf'">[PDF]</xsl:when>
                    <xsl:otherwise>[   ]</xsl:otherwise>
                  </xsl:choose>
                </td>
                <td class="col-name">
                  <a href="{@urlPath}"><xsl:value-of select="$name"/></a>
                </td>
                <td class="col-date"><xsl:value-of select="@date"/></td>
                <td class="col-size"><xsl:value-of select="@size"/></td>
              </tr>
            </xsl:for-each>
          </tbody>
        </table>
        <hr class="bottom"/>
        <p class="address">Apache Tomcat/8.5.68</p>
      </body>
    </html>
  </xsl:template>

</xsl:stylesheet>
