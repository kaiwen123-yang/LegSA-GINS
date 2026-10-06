param(
 [Parameter(Mandatory=$true)][string]$DocxPath,
 [Parameter(Mandatory=$true)][string]$PdfPath,
 [Parameter(Mandatory=$true)][string]$ReceiptPath
)
$ErrorActionPreference = 'Stop'
if (Test-Path -LiteralPath $PdfPath) { throw 'PDF output already exists' }
$before = (Get-FileHash -LiteralPath $DocxPath -Algorithm SHA256).Hash.ToLower()
$wordApp = $null
$workingDoc = $null
try {
 $wordApp = New-Object -ComObject Word.Application
 $wordApp.Visible = $false
 $wordApp.DisplayAlerts = 0
 $wordApp.AutomationSecurity = 3
 $workingDoc = $wordApp.Documents.Open($DocxPath, $false, $false)
 $workingDoc.Repaginate()
 $workingDoc.Fields.Update() | Out-Null
 foreach ($section in $workingDoc.Sections) {
  foreach ($footer in $section.Footers) {
   $footer.Range.Fields.Update() | Out-Null
  }
 }
 $workingDoc.Save()
 $workingDoc.ExportAsFixedFormat($PdfPath, 17)
 $receipt = [ordered]@{
  renderer = 'Microsoft Word native PDF export'
  word_version = $wordApp.Version
  pages = $workingDoc.ComputeStatistics(2)
  words_word_reported = $workingDoc.ComputeStatistics(0)
  source_docx_before_field_refresh_sha256 = $before
  fields_refreshed = $true
  scientific_execution = 0
  visual_review = 'PENDING'
 }
} finally {
 if ($null -ne $workingDoc) { $workingDoc.Close(0); [void][Runtime.InteropServices.Marshal]::ReleaseComObject($workingDoc) }
 if ($null -ne $wordApp) { $wordApp.Quit(); [void][Runtime.InteropServices.Marshal]::ReleaseComObject($wordApp) }
}

$receipt['source_docx_after_field_refresh_sha256'] = (Get-FileHash -LiteralPath $DocxPath -Algorithm SHA256).Hash.ToLower()
$receipt['pdf_sha256'] = (Get-FileHash -LiteralPath $PdfPath -Algorithm SHA256).Hash.ToLower()
$receipt | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $ReceiptPath -Encoding utf8
$receipt | ConvertTo-Json -Compress
