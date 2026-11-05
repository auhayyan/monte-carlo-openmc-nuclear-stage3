param(
    [ValidateSet('Check', 'Smoke', 'Scatter')]
    [string]$Action = 'Smoke',
    [string]$OutputDirectory = '',
    [ValidateRange(1, 64)]
    [int]$Threads = 2
)

$ErrorActionPreference = 'Stop'
$projectRoot = [IO.Path]::GetFullPath($PSScriptRoot)
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw 'Docker is not available. Install Docker Desktop, start it, and open a new PowerShell window.'
}
$containerType = & docker info --format '{{.OSType}}'
if ($LASTEXITCODE -ne 0) {
    throw 'Docker is not ready. Start Docker Desktop and wait for the engine to run.'
}
if ($containerType.Trim() -ne 'linux') {
    throw 'Switch Docker Desktop to Linux containers, then retry.'
}

$lockPath = Join-Path $projectRoot 'image-lock.txt'
$requestedImage = 'openmc/openmc:latest'
if (Test-Path -LiteralPath $lockPath) {
    $requestedImage = (Get-Content -LiteralPath $lockPath -Raw).Trim()
    if (-not $requestedImage.StartsWith('openmc/openmc@sha256:')) {
        throw 'image-lock.txt must contain an openmc/openmc@sha256:... image reference.'
    }
}
& docker pull $requestedImage
if ($LASTEXITCODE -ne 0) {
    throw 'The OpenMC image download failed. Check the connection and the Docker error above.'
}
$lockedImage = & docker image inspect $requestedImage --format '{{index .RepoDigests 0}}'
if ($LASTEXITCODE -ne 0 -or -not $lockedImage.StartsWith('openmc/openmc@sha256:')) {
    throw 'Could not resolve the downloaded OpenMC image to its immutable digest.'
}
if (-not (Test-Path -LiteralPath $lockPath)) {
    Set-Content -LiteralPath $lockPath -Value $lockedImage -Encoding ascii
}

& docker run --rm --entrypoint openmc $lockedImage --version
if ($LASTEXITCODE -ne 0) {
    throw 'The OpenMC executable check failed.'
}
& docker run --rm --entrypoint python3 $lockedImage -c 'import openmc; print(openmc.__version__)'
if ($LASTEXITCODE -ne 0) {
    throw 'The OpenMC Python-interface check failed.'
}
if ($Action -eq 'Check') {
    Write-Output 'Docker and OpenMC checks passed. The exact image is recorded in image-lock.txt.'
    return
}

if ([string]::IsNullOrWhiteSpace($OutputDirectory)) {
    $runStamp = [DateTime]::UtcNow.ToString('yyyyMMdd-HHmmss')
    $OutputDirectory = 'runs/' + $Action.ToLowerInvariant() + '-' + $runStamp
}
if ([IO.Path]::IsPathRooted($OutputDirectory)) {
    throw 'Choose a relative output path inside this project folder.'
}
$resolvedOutput = [IO.Path]::GetFullPath((Join-Path $projectRoot $OutputDirectory))
$projectPrefix = $projectRoot.TrimEnd([IO.Path]::DirectorySeparatorChar) + [IO.Path]::DirectorySeparatorChar
if (-not $resolvedOutput.StartsWith($projectPrefix, [StringComparison]::OrdinalIgnoreCase)) {
    throw 'The output path must stay inside the project folder.'
}
if (Test-Path -LiteralPath $resolvedOutput) {
    throw 'That output directory already exists. Choose a new name to preserve the previous run.'
}
$relativeOutput = $resolvedOutput.Substring($projectPrefix.Length).Replace('\', '/')
$dockerArguments = @(
    'run', '--rm',
    '--mount', ('type=bind,source=' + $projectRoot + ',target=/work'),
    '--workdir', '/work',
    '--env', ('OPENMC_STARTER_IMAGE=' + $lockedImage),
    '--entrypoint', 'python3',
    $lockedImage, 'benchmark.py',
    '--output', $relativeOutput,
    '--threads', $Threads.ToString()
)
if ($Action -eq 'Scatter') {
    $dockerArguments += @('--scatter-ratio', '0.8', '--batches', '100', '--particles', '10000')
}
& docker @dockerArguments
if ($LASTEXITCODE -ne 0) {
    throw 'OpenMC stopped. Keep the run folder and check the error above.'
}
Write-Output ('Windows results folder: ' + $resolvedOutput)
