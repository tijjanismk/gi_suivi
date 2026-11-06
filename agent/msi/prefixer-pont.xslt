<?xml version="1.0" encoding="utf-8"?>
<!--
  Transformation appliquée par heat à la moisson de dist\gisuivi-agent\_pont (construire-msi.ps1).
  heat tire ses identifiants des chemins relatifs au dossier moissonné ; _pont et _internal contiennent
  les mêmes noms (python314.dll, base_library.zip…) : sans préfixe, light refuserait les doublons.
  Tout identifiant créé par heat reçoit le préfixe « pont_ » ; la référence au dossier PONT
  (déclaré dans Produit.wxs) reste telle quelle.
-->
<xsl:stylesheet version="1.0"
                xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
                xmlns:wix="http://schemas.microsoft.com/wix/2006/wi">
  <xsl:output method="xml" indent="yes" encoding="utf-8" />

  <xsl:template match="@* | node()">
    <xsl:copy>
      <xsl:apply-templates select="@* | node()" />
    </xsl:copy>
  </xsl:template>

  <xsl:template match="wix:Component/@Id | wix:ComponentRef/@Id | wix:File/@Id | wix:Directory/@Id">
    <xsl:attribute name="Id">
      <xsl:value-of select="concat('pont_', .)" />
    </xsl:attribute>
  </xsl:template>

  <xsl:template match="wix:Component/@Directory[. != 'PONT']">
    <xsl:attribute name="Directory">
      <xsl:value-of select="concat('pont_', .)" />
    </xsl:attribute>
  </xsl:template>
</xsl:stylesheet>
