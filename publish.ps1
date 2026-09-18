param([Parameter(Mandatory=$true)][string]$RepoUrl)
if (!(Test-Path .git)) { git init }
git add .
git commit -m "Build clinic appointment and patient management system"
git branch -M main
$hasOrigin = git remote | Select-String '^origin$'
if ($hasOrigin) { git remote set-url origin $RepoUrl } else { git remote add origin $RepoUrl }
git push -u origin main
