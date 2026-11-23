param(
  [string]$OutputRoot = (Join-Path $PSScriptRoot '../output'),
  [switch]$Apply
)

$ErrorActionPreference = 'Stop'
$releaseRoot = (Resolve-Path -LiteralPath $OutputRoot).Path.TrimEnd('\', '/')
$utf8 = [System.Text.UTF8Encoding]::new($false)

function In-Output([string]$Relative) {
  $path = [System.IO.Path]::GetFullPath((Join-Path $releaseRoot $Relative))
  if (-not $path.StartsWith($releaseRoot + [System.IO.Path]::DirectorySeparatorChar, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Path escapes the named output directory: $Relative"
  }
  return $path
}

function Write-Text([string]$Relative, [string]$Content) {
  [System.IO.File]::WriteAllText((In-Output $Relative), $Content, $utf8)
}

$marker = '<!-- esafe-versioned-output -->'
$readmePath = In-Output 'README.md'
$organized = (Test-Path -LiteralPath $readmePath) -and ((Get-Content -LiteralPath $readmePath -Raw).Contains($marker))
if ((Test-Path -LiteralPath $readmePath) -and -not $organized) { throw 'An existing unrecognized README.md needs review before organization.' }

$legacy = @{
  'READ-ME.txt' = 'v0.1.0'
  'verification.json' = 'v0.1.0'
  'installer-build.log' = 'v0.1.0'
  'Esafe-POS-Workstation-Setup.txt' = 'v0.2.0'
  'Esafe-POS-Cash-Drawer-Kit-README.txt' = 'v0.2.1'
  'POS-Cash-Drawer-Implementation-Prompt.txt' = 'v0.2.1'
}
$plan = @()
foreach ($item in Get-ChildItem -LiteralPath $releaseRoot -Force) {
  if ($item.Name -match '^v\d+\.\d+\.\d+$' -and $item.PSIsContainer) { continue }
  if ($item.Name -eq 'README.md') { continue }
  if ($item.Name -eq 'SHA256SUMS.txt') {
    if ($organized) { continue }
    $destination = 'v0.2.0/SHA256SUMS-flat-layout.txt'
  } elseif ($legacy.ContainsKey($item.Name)) {
    $destination = $legacy[$item.Name] + '/' + $item.Name
  } elseif ($item.Name -match '(?<!\d)(\d+\.\d+\.\d+)(?!\d)') {
    $destination = 'v' + $Matches[1] + '/' + $item.Name
  } else { throw "Unclassified output item: $($item.Name). Assign its release before moving files." }
  $sourcePath = In-Output $item.Name
  $targetPath = In-Output $destination
  if (Test-Path -LiteralPath $targetPath) { throw "Destination already exists; no overwrite permitted: $destination" }
  $entries = @($item)
  if ($item.PSIsContainer) { $entries += @(Get-ChildItem -LiteralPath $sourcePath -Force -Recurse) }
  if ($entries | Where-Object { $_.Attributes -band [System.IO.FileAttributes]::ReparsePoint }) { throw "Reparse point needs review: $($item.Name)" }
  $plan += [PSCustomObject]@{ Source = $item.Name; Destination = $destination; Directory = $item.PSIsContainer }
}

if (-not $Apply) {
  [PSCustomObject]@{ Output = $releaseRoot; DryRun = $true; Moves = $plan } | ConvertTo-Json -Depth 5
  return
}

# Snapshot every original artifact's contents before any move. Directories are
# moved within this verified output root, never deleted or replaced.
$before = @()
foreach ($entry in $plan) {
  $source = In-Output $entry.Source
  $files = if ($entry.Directory) { @(Get-ChildItem -LiteralPath $source -Recurse -File -Force) } else { @(Get-Item -LiteralPath $source) }
  foreach ($file in $files) {
    $suffix = if ($entry.Directory) { $file.FullName.Substring($source.Length).TrimStart('\', '/') } else { '' }
    $target = if ($suffix) { Join-Path $entry.Destination $suffix } else { $entry.Destination }
    $null = In-Output $target
    $before += [PSCustomObject]@{ Target = $target; SHA256 = (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash }
  }
}
foreach ($entry in $plan) {
  $source = In-Output $entry.Source
  $target = In-Output $entry.Destination
  $parent = Split-Path -Parent $target
  if (-not (Test-Path -LiteralPath $parent)) { $null = New-Item -ItemType Directory -Path $parent }
  Move-Item -LiteralPath $source -Destination $target
}
foreach ($entry in $before) {
  if ((Get-FileHash -LiteralPath (In-Output $entry.Target) -Algorithm SHA256).Hash -ne $entry.SHA256) {
    throw "Artifact verification failed: $($entry.Target)"
  }
}

$releases = @(Get-ChildItem -LiteralPath $releaseRoot -Directory | Where-Object { $_.Name -match '^v\d+\.\d+\.\d+$' } | Sort-Object { [version]$_.Name.Substring(1) } -Descending)
$sdkCopies = @()
foreach ($release in $releases) {
  $version = $release.Name.Substring(1)
  $manifest = In-Output ($release.Name + '/installer-release-' + $version + '.json')
  if (-not (Test-Path -LiteralPath $manifest)) { continue }
  $metadata = Get-Content -LiteralPath $manifest -Raw | ConvertFrom-Json
  if (-not $metadata.sdkVersion) { continue }
  $package = 'esafe-printer-manager-' + $metadata.sdkVersion + '.tgz'
  $target = In-Output ($release.Name + '/' + $package)
  $source = In-Output ('v' + $metadata.sdkVersion + '/' + $package)
  if (-not (Test-Path -LiteralPath $target)) {
    if (-not (Test-Path -LiteralPath $source)) { throw "Required SDK package not found: $package" }
    Copy-Item -LiteralPath $source -Destination $target
    $sdkCopies += $release.Name + '/' + $package
  }
  if ((Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash -ne (Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash) { throw "SDK copy differs: $target" }
}

$index = @($marker, '# Esafe Printer Manager releases', '', 'Release artifacts are grouped by manager version. Open the newest version folder for its installer, integration kit and verification records.', '', '| Release | Installer |', '|---|---|')
foreach ($release in $releases) {
  $version = $release.Name.Substring(1)
  $installer = 'Esafe-Printer-Manager-' + $version + '-windows-x64-setup.exe'
  $link = if (Test-Path -LiteralPath (In-Output ($release.Name + '/' + $installer))) { '[Windows x64 installer](' + $release.Name + '/' + $installer + ')' } else { 'See release folder' }
  $index += '| [' + $release.Name + '](' + $release.Name + '/) | ' + $link + ' |'
}
$index += @('', 'Manager 0.2.1 uses SDK 0.2.0; an identical copy is included in v0.2.1 for a self-contained release folder.', '', 'Each release has SHA256SUMS.txt. The root SHA256SUMS.txt indexes every current release file and this README. Checksums establish file integrity, not publisher signing or hardware qualification.', '', 'The original mixed-version checksum manifest is preserved at v0.2.0/SHA256SUMS-flat-layout.txt as a historical record. Version-specific original manifests, installers, archives and verification records retain their original contents.', '', 'Future flat output can be reviewed with npm run output:organize and organized with npm run output:organize -- -Apply. No files are deleted or overwritten.')
Write-Text 'README.md' (($index -join "`n") + "`n")

foreach ($release in $releases) {
  $lines = @(Get-ChildItem -LiteralPath $release.FullName -Recurse -File -Force | Where-Object { $_.Name -notlike 'SHA256SUMS*.txt' } | Sort-Object FullName | ForEach-Object {
    (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant() + '  ' + $_.FullName.Substring($release.FullName.Length + 1).Replace('\', '/')
  })
  Write-Text ($release.Name + '/SHA256SUMS.txt') (($lines -join "`n") + "`n")
}
$allFiles = @((Get-Item -LiteralPath $readmePath)) + @(foreach ($release in $releases) { Get-ChildItem -LiteralPath $release.FullName -Recurse -File -Force })
$allLines = @($allFiles | Sort-Object FullName | ForEach-Object {
  (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant() + '  ' + $_.FullName.Substring($releaseRoot.Length + 1).Replace('\', '/')
})
Write-Text 'SHA256SUMS.txt' (($allLines -join "`n") + "`n")
[PSCustomObject]@{ Output = $releaseRoot; MovedItems = $plan.Count; VerifiedOriginalFiles = $before.Count; Releases = @($releases.Name); CopiedSDK = $sdkCopies; IndexedFiles = $allFiles.Count } | ConvertTo-Json -Depth 4
