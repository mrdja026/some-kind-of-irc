$ErrorActionPreference = "Stop"

$InfraRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $InfraRoot
$BinDir = Join-Path $InfraRoot "bin"
$CacheDir = Join-Path $InfraRoot "cache"
$ExtractDir = Join-Path $InfraRoot "memurai"

function Ensure-Dir {
    param([string]$Path)
    if (-not (Test-Path $Path)) {
        New-Item -ItemType Directory -Path $Path | Out-Null
    }
}

function Remove-IfExists {
    param([string]$Path)
    if (Test-Path $Path) {
        Remove-Item -Path $Path -Recurse -Force
    }
}

function Download-File {
    param(
        [string]$Url,
        [string]$Destination
    )

    $tmp = "$Destination.part"
    Remove-IfExists -Path $tmp
    try {
        Invoke-WebRequest -Uri $Url -OutFile $tmp
        Move-Item -Path $tmp -Destination $Destination -Force
    }
    catch {
        Remove-IfExists -Path $tmp
        throw
    }
}

function Write-RedisShim {
    param([string]$Path)

    @"
@echo off
"%~dp0memurai.exe" %*
"@ | Set-Content -Path $Path -Encoding ascii
}

Ensure-Dir -Path $BinDir
Ensure-Dir -Path $CacheDir

$minioUrl = "https://dl.min.io/server/minio/release/windows-amd64/minio.exe"
$minioExe = Join-Path $BinDir "minio.exe"

if (-not (Test-Path $minioExe)) {
    Write-Host "Downloading MinIO..." -ForegroundColor Yellow
    try {
        Download-File -Url $minioUrl -Destination $minioExe
    }
    catch {
        Remove-IfExists -Path $minioExe
        Write-Error "MinIO download failed."
        exit 1
    }
    Write-Host "MinIO ready: $minioExe" -ForegroundColor Green
}
else {
    Write-Host "MinIO already present: $minioExe" -ForegroundColor DarkGray
}

$redisExeTarget = Join-Path $BinDir "redis-server.exe"
$redisCmdTarget = Join-Path $BinDir "redis-server.cmd"
$memuraiExeTarget = Join-Path $BinDir "memurai.exe"

$memuraiUrl = "https://dist.memurai.com/releases/Memurai-Developer/4.2.2/Memurai-for-Redis-v4.2.2.msi"
$memuraiMsi = Join-Path $CacheDir "Memurai-for-Redis-v4.2.2.msi"

$redisReady = $false

if (Test-Path $redisExeTarget) {
    Write-Host "Redis server binary already present: $redisExeTarget" -ForegroundColor DarkGray
    $redisReady = $true
}
elseif (Test-Path $memuraiExeTarget) {
    if (-not (Test-Path $redisCmdTarget)) {
        Write-RedisShim -Path $redisCmdTarget
        Write-Host "Redis shim ready: $redisCmdTarget" -ForegroundColor Green
    }
    Write-Host "Memurai binary already present: $memuraiExeTarget" -ForegroundColor DarkGray
    $redisReady = $true
}

if (-not $redisReady) {
    $redisCandidate = $null
    $memuraiCandidate = $null

    if (Test-Path $ExtractDir) {
        $redisCandidate = Get-ChildItem -Path $ExtractDir -Filter "redis-server.exe" -Recurse -File -ErrorAction SilentlyContinue | Select-Object -First 1
        $memuraiCandidate = Get-ChildItem -Path $ExtractDir -Filter "memurai.exe" -Recurse -File -ErrorAction SilentlyContinue | Select-Object -First 1

        if ($null -ne $redisCandidate -or $null -ne $memuraiCandidate) {
            Write-Host "Using extracted Memurai package already present: $ExtractDir" -ForegroundColor DarkGray
        }
        else {
            Write-Host "Existing Memurai extract missing binaries, re-extracting..." -ForegroundColor Yellow
        }
    }

    if ($null -eq $redisCandidate -and $null -eq $memuraiCandidate) {
        if (-not (Test-Path $memuraiMsi)) {
            Write-Host "Downloading Memurai Developer MSI..." -ForegroundColor Yellow
            try {
                Download-File -Url $memuraiUrl -Destination $memuraiMsi
            }
            catch {
                Remove-IfExists -Path $memuraiMsi
                Write-Error "Memurai download failed."
                exit 1
            }
            Write-Host "Memurai MSI ready: $memuraiMsi" -ForegroundColor Green
        }
        else {
            Write-Host "Memurai MSI already present: $memuraiMsi" -ForegroundColor DarkGray
        }

        Write-Host "Extracting Memurai MSI..." -ForegroundColor Yellow
        $extractTmpDir = Join-Path $InfraRoot "memurai.tmp"
        Remove-IfExists -Path $extractTmpDir
        Ensure-Dir -Path $extractTmpDir

        try {
            $msiArgs = @(
                "/a",
                "`"$memuraiMsi`"",
                "/qn",
                "TARGETDIR=`"$extractTmpDir`""
            )
            $proc = Start-Process -FilePath "msiexec.exe" -ArgumentList $msiArgs -Wait -PassThru
            if ($proc.ExitCode -ne 0) {
                throw "msiexec exited with code $($proc.ExitCode)"
            }

            Remove-IfExists -Path $ExtractDir
            Move-Item -Path $extractTmpDir -Destination $ExtractDir
        }
        catch {
            Remove-IfExists -Path $extractTmpDir
            Write-Error "Memurai extraction failed."
            exit 1
        }

        $redisCandidate = Get-ChildItem -Path $ExtractDir -Filter "redis-server.exe" -Recurse -File -ErrorAction SilentlyContinue | Select-Object -First 1
        $memuraiCandidate = Get-ChildItem -Path $ExtractDir -Filter "memurai.exe" -Recurse -File -ErrorAction SilentlyContinue | Select-Object -First 1
    }

    if ($null -ne $redisCandidate) {
        Copy-Item -Path $redisCandidate.FullName -Destination $redisExeTarget -Force
        Write-Host "Redis server binary ready: $redisExeTarget" -ForegroundColor Green
    }
    elseif ($null -ne $memuraiCandidate) {
        Copy-Item -Path $memuraiCandidate.FullName -Destination $memuraiExeTarget -Force
        Write-RedisShim -Path $redisCmdTarget
        Write-Host "Memurai binary ready: $memuraiExeTarget" -ForegroundColor Green
        Write-Host "Redis shim ready: $redisCmdTarget" -ForegroundColor Green
    }
    else {
        Write-Error "Could not locate redis-server.exe or memurai.exe in extracted Memurai package."
        exit 1
    }
}

Write-Host "Infra bootstrap completed." -ForegroundColor Cyan
Write-Host "- MinIO: $minioExe"
Write-Host "- Redis: $redisExeTarget (or $redisCmdTarget)"
Write-Host "- Memurai MSI cache: $memuraiMsi"
