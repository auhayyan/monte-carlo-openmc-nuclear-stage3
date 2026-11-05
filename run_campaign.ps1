param(
    [ValidateRange(1, 100)]
    [int]$Repetitions = 3,
    [ValidateRange(30, 100000)]
    [int]$Batches = 100,
    [ValidateRange(1, 10000000)]
    [int]$Particles = 10000,
    [ValidateRange(1, 64)]
    [int]$Threads = 2
)

$ErrorActionPreference = 'Stop'
$projectRoot = [IO.Path]::GetFullPath($PSScriptRoot)
& powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $projectRoot 'run.ps1') -Action Check
if ($LASTEXITCODE -ne 0) {
    throw 'Docker/OpenMC checks failed. The campaign has not started.'
}
$image = (Get-Content -LiteralPath (Join-Path $projectRoot 'image-lock.txt') -Raw).Trim()
$campaignName = 'scattering-study-' + [DateTime]::UtcNow.ToString('yyyyMMdd-HHmmss')
$campaignRelative = 'runs/' + $campaignName
$campaignRoot = Join-Path $projectRoot $campaignRelative
New-Item -ItemType Directory -Path $campaignRoot | Out-Null
$manifest = [ordered]@{
    status = 'started'
    started_utc = [DateTime]::UtcNow.ToString('o')
    image = $image
    sigma_t_per_cm = 1.0
    scatter_ratio = 0.8
    thicknesses_cm = @(0.25, 0.5, 1.0, 2.0, 3.0)
    repetitions_per_thickness = $Repetitions
    batches = $Batches
    particles_per_batch = $Particles
    threads = $Threads
    first_seed = 2026110501
    benchmark_sha256 = (Get-FileHash -LiteralPath (Join-Path $projectRoot 'benchmark.py') -Algorithm SHA256).Hash.ToLowerInvariant()
    launcher_sha256 = (Get-FileHash -LiteralPath $PSCommandPath -Algorithm SHA256).Hash.ToLowerInvariant()
}
$manifest | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $campaignRoot 'campaign.json') -Encoding utf8
$records = @()
$caseNumber = 0
foreach ($thickness in $manifest.thicknesses_cm) {
    foreach ($replicate in 1..$Repetitions) {
        $caseNumber += 1
        $caseName = 'case-{0:D2}' -f $caseNumber
        $caseRelative = $campaignRelative + '/' + $caseName
        $caseRoot = Join-Path $campaignRoot $caseName
        $runSeed = 2026110500 + $caseNumber
        $thicknessArgument = $thickness.ToString([Globalization.CultureInfo]::InvariantCulture)
        $dockerArguments = @(
            'run', '--rm',
            '--mount', ('type=bind,source=' + $projectRoot + ',target=/work'),
            '--workdir', '/work',
            '--env', ('OPENMC_STARTER_IMAGE=' + $image),
            '--entrypoint', 'python3', $image, 'benchmark.py',
            '--scatter-ratio', '0.8',
            '--sigma', '1.0',
            '--thickness', $thicknessArgument,
            '--batches', $Batches.ToString(),
            '--particles', $Particles.ToString(),
            '--seed', $runSeed.ToString(),
            '--threads', $Threads.ToString(),
            '--output', $caseRelative
        )
        & docker @dockerArguments | Tee-Object -FilePath (Join-Path $campaignRoot ($caseName + '.log'))
        if ($LASTEXITCODE -ne 0) {
            throw ('Stopped at ' + $caseName + '. Preserve the campaign and error output; completed cases remain saved.')
        }
        $resultPath = Join-Path $caseRoot 'results.json'
        $result = Get-Content -LiteralPath $resultPath -Raw | ConvertFrom-Json
        $records += [pscustomobject]@{
            Case = $caseName
            Thickness = $result.configuration.thickness_cm
            Seed = $result.configuration.seed
            Histories = $result.configuration.histories
            Total = $result.transmission
            TotalSE = $result.transmission_standard_error
            Uncollided = $result.uncollided_transmission
            UncollidedSE = $result.uncollided_transmission_standard_error
            Reference = $result.configuration.analytical_uncollided_transmission
            Reflection = $result.reflection
            ReflectionSE = $result.reflection_standard_error
            Absorption = $result.absorption
            AbsorptionSE = $result.absorption_standard_error
            Balance = $result.particle_balance
            Review = $result.review_needed
        }
        $records | Export-Csv -LiteralPath (Join-Path $campaignRoot 'overview.csv') -NoTypeInformation -Encoding utf8
    }
}
$manifest.status = 'completed'
$manifest.completed_utc = [DateTime]::UtcNow.ToString('o')
$manifest.completed_cases = $records.Count
$manifest | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $campaignRoot 'campaign.json') -Encoding utf8
$records | Format-Table Thickness,Seed,@{Label='T';Expression={ '{0:F6}' -f $_.Total }},@{Label='T0';Expression={ '{0:F6}' -f $_.Uncollided }},@{Label='R';Expression={ '{0:F6}' -f $_.Reflection }},@{Label='A';Expression={ '{0:F6}' -f $_.Absorption }},Review -AutoSize
Write-Output ('Campaign saved to: ' + $campaignRoot)
Write-Output 'Keep the complete campaign, including flagged runs.'
