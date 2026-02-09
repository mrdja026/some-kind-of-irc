$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir
Set-Location $ProjectRoot

Write-Host "Working directory set to: $ProjectRoot" -ForegroundColor Gray
Write-Host "Starting IRC Fullstack Local Environment (Windows)..." -ForegroundColor Cyan

function Stop-AllServices {
    Write-Host "`nStopping all services..." -ForegroundColor Yellow
    Get-Job | Stop-Job
    Get-Job | Remove-Job
    Write-Host "All services stopped." -ForegroundColor Green
}

function Resolve-RedisBinary {
    param([string]$ProjectRootPath)

    $candidates = @(
        (Join-Path $ProjectRootPath "infra_resource\bin\redis-server.exe"),
        (Join-Path $ProjectRootPath "infra_resource\bin\redis-server.cmd"),
        (Join-Path $ProjectRootPath "redis-server.exe")
    )

    foreach ($candidate in $candidates) {
        if (Test-Path $candidate) {
            return $candidate
        }
    }

    $cmd = Get-Command "redis-server" -ErrorAction SilentlyContinue
    if ($null -ne $cmd) {
        return $cmd.Source
    }

    return $null
}

$BootstrapScript = Join-Path $ProjectRoot "infra_resource\bootstrap-windows.ps1"
$MinioPath = Join-Path $ProjectRoot "infra_resource\bin\minio.exe"
$RedisPath = Resolve-RedisBinary -ProjectRootPath $ProjectRoot

if (-not (Test-Path $BootstrapScript)) {
    Write-Error "Missing bootstrap script: $BootstrapScript"
    exit 1
}

if ((-not (Test-Path $MinioPath)) -or ($null -eq $RedisPath)) {
    Write-Host "Missing infra binaries. Running bootstrap..." -ForegroundColor Yellow
    & powershell -NoProfile -ExecutionPolicy Bypass -File $BootstrapScript
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Infra bootstrap failed."
        exit 1
    }
    $RedisPath = Resolve-RedisBinary -ProjectRootPath $ProjectRoot
}

if (-not (Test-Path $MinioPath)) {
    Write-Error "MinIO binary not found at $MinioPath"
    exit 1
}

if ($null -eq $RedisPath) {
    Write-Error "Redis binary not found after bootstrap."
    exit 1
}

$BackendPython = Join-Path $ProjectRoot "backend\be\Scripts\python.exe"
if (-not (Test-Path $BackendPython)) {
    Write-Error "Backend virtual environment not found at $BackendPython. Run 'pixi run setup-windows'."
    exit 1
}

$SeedUsersScript = Join-Path $ProjectRoot "backend\create_test_user.py"
$SeedUsersFile = Join-Path $ProjectRoot "backend\seed_users.json"

$PixiPython = Join-Path $ProjectRoot ".pixi\envs\default\python.exe"
if (-not (Test-Path $PixiPython)) {
    $PixiPython = $BackendPython
}

$PnpmPath = Join-Path $ProjectRoot ".pixi\envs\default\Library\bin\pnpm.bat"
if (-not (Test-Path $PnpmPath)) {
    $PnpmPath = Join-Path $ProjectRoot ".pixi\envs\default\Scripts\pnpm.cmd"
    if (-not (Test-Path $PnpmPath)) {
        $pnpmCmd = Get-Command "pnpm" -ErrorAction SilentlyContinue
        if ($null -eq $pnpmCmd) {
            Write-Error "pnpm not found. Install dependencies with 'pixi run setup-windows'."
            exit 1
        }
        $PnpmPath = $pnpmCmd.Source
    }
}

$MinioDataPath = Join-Path $ProjectRoot "media-storage\data"
if (-not (Test-Path $MinioDataPath)) {
    New-Item -ItemType Directory -Path $MinioDataPath | Out-Null
}

Write-Host "Starting MinIO..." -ForegroundColor Green
Start-Job -Name "MinIO" -ScriptBlock {
    param($ExePath, $DataPath, $Root)
    $env:MINIO_ROOT_USER = "minioadmin"
    $env:MINIO_ROOT_PASSWORD = "minioadmin"
    Set-Location $Root
    & $ExePath server $DataPath --console-address :9001
} -ArgumentList $MinioPath, $MinioDataPath, $ProjectRoot | Out-Null

Write-Host "Starting Redis..." -ForegroundColor Green
Start-Job -Name "Redis" -ScriptBlock {
    param($ExePath, $Root)
    Set-Location $Root
    & $ExePath --port 6379
} -ArgumentList $RedisPath, $ProjectRoot | Out-Null

Start-Sleep -Seconds 2

Write-Host "Starting Backend..." -ForegroundColor Green
$BackendEnv = @{
    MEDIA_STORAGE_URL = "http://localhost:9101"
    ALLOWED_ORIGINS = "http://localhost:3000,http://127.0.0.1:3000,http://localhost:5173"
    REDIS_URL = "redis://localhost:6379/0"
    DATA_PROCESSOR_URL = "http://localhost:8003"
    AUDIT_LOGGER_URL = "http://localhost:8004"
}

Start-Job -Name "Backend" -ScriptBlock {
    param($EnvVars, $PyPath, $Root)
    foreach ($key in $EnvVars.Keys) { Set-Item "env:$key" $EnvVars[$key] }
    Set-Location $Root
    & $PyPath -m uvicorn src.main:app --reload --reload-dir backend --host 0.0.0.0 --port 8002 --app-dir backend
} -ArgumentList $BackendEnv, $BackendPython, $ProjectRoot | Out-Null

if ((Test-Path $SeedUsersScript) -and (Test-Path $SeedUsersFile)) {
    Start-Sleep -Seconds 2
    Write-Host "Seeding default users from backend/seed_users.json..." -ForegroundColor Green
    & $BackendPython $SeedUsersScript --file $SeedUsersFile
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "User seeding failed (exit code $LASTEXITCODE). Run 'pixi run seed-users-windows' manually."
    }
}
else {
    Write-Host "Skipping user seeding (missing backend/create_test_user.py or backend/seed_users.json)." -ForegroundColor DarkGray
}

Write-Host "Starting Media Storage..." -ForegroundColor Green
$MediaEnv = @{
    MINIO_ENDPOINT = "http://localhost:9000"
    MINIO_PUBLIC_ENDPOINT = "http://localhost:9000"
    MINIO_BUCKET = "irc-media"
    MINIO_REGION = "us-east-1"
    MINIO_USE_SSL = "false"
    MINIO_ACCESS_KEY = "minioadmin"
    MINIO_SECRET_KEY = "minioadmin"
    BACKEND_VERIFY_URL = "http://localhost:8002/auth/me"
    PUBLIC_BASE_URL = "http://localhost:9101"
    MAX_UPLOAD_MB = "10"
    PORT = "9101"
}

Start-Job -Name "MediaStorage" -ScriptBlock {
    param($EnvVars, $PyPath, $Root)
    foreach ($key in $EnvVars.Keys) { Set-Item "env:$key" $EnvVars[$key] }
    Set-Location $Root
    & $PyPath media-storage/app.py
} -ArgumentList $MediaEnv, $PixiPython, $ProjectRoot | Out-Null

Write-Host "Skipping Data Processor (Windows incompatibility)..." -ForegroundColor DarkGray

Write-Host "Starting Audit Logger..." -ForegroundColor Green
Start-Job -Name "AuditLogger" -ScriptBlock {
    param($PyPath, $Root)
    $env:PORT = "8004"
    Set-Location $Root
    & $PyPath audit-logger/main.py
} -ArgumentList $PixiPython, $ProjectRoot | Out-Null

Write-Host "Starting Frontend..." -ForegroundColor Green
$FrontendEnv = @{
    VITE_API_URL = "http://localhost:8002"
    VITE_WS_URL = "ws://localhost:8002"
    VITE_PUBLIC_API_URL = "http://localhost:8002"
    VITE_PUBLIC_WS_URL = "ws://localhost:8002"
}

Start-Job -Name "Frontend" -ScriptBlock {
    param($EnvVars, $PnpmExe, $Root)
    foreach ($key in $EnvVars.Keys) { Set-Item "env:$key" $EnvVars[$key] }
    Set-Location (Join-Path $Root "frontend")
    & $PnpmExe dev
} -ArgumentList $FrontendEnv, $PnpmPath, $ProjectRoot | Out-Null

Write-Host "`nAll services started! Streaming logs... (Press Ctrl+C to stop)" -ForegroundColor Cyan
Write-Host "Frontend: http://localhost:3000" -ForegroundColor Green
Write-Host "Backend: http://localhost:8002" -ForegroundColor Green
Write-Host "MinIO Console: http://localhost:9001" -ForegroundColor Green
Write-Host "Audit Logger: http://localhost:8004" -ForegroundColor Green

try {
    while ($true) {
        $jobs = Get-Job
        foreach ($job in $jobs) {
            if ($job.HasMoreData) {
                Receive-Job -Job $job *>&1 | ForEach-Object {
                    Write-Host "[$($job.Name)] $_" -ForegroundColor Green
                }
            }
        }

        Start-Sleep -Milliseconds 500

        $criticalJobs = @("MinIO", "Redis", "Backend", "MediaStorage", "AuditLogger", "Frontend")
        $failed = @()
        foreach ($jobName in $criticalJobs) {
            $job = Get-Job -Name $jobName -ErrorAction SilentlyContinue
            if ($null -eq $job) { continue }
            if ($job.State -eq "Failed" -or $job.State -eq "Stopped") {
                $failed += $jobName
            }
        }

        if ($failed.Count -gt 0) {
            Write-Error ("Critical service(s) failed/stopped: " + ($failed -join ", "))
            break
        }
    }
}
catch [System.Management.Automation.PipelineStoppedException] {
}
finally {
    Stop-AllServices
}
