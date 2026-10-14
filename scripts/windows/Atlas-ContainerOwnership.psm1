function ConvertFrom-AtlasContainerInspection(
    [string]$Name,
    [string]$ExpectedService,
    [string]$ExpectedRoot,
    [string]$InspectionJson
) {
    try {
        $container = $InspectionJson | ConvertFrom-Json -ErrorAction Stop
    } catch {
        throw "Docker inspection for $Name returned malformed JSON: $($_.Exception.Message)"
    }

    if (-not $container -or -not $container.Name -or -not $container.Config -or
        -not $container.Config.Labels -or -not $container.State) {
        throw "Docker inspection for $Name is missing container identity, labels, or state."
    }

    $labels = $container.Config.Labels
    $project = [string]$labels.'com.docker.compose.project'
    $service = [string]$labels.'com.docker.compose.service'
    $workingDirectory = [string]$labels.'com.docker.compose.project.working_dir'
    $configFiles = [string]$labels.'com.docker.compose.project.config_files'
    $expectedComposeFile = Join-Path $ExpectedRoot "docker-compose.yml"
    $containerName = [string]$container.Name
    if (-not $containerName.StartsWith("/")) { $containerName = "/$containerName" }

    $projectMatches = @("atlas", "projectatlas") -contains $project
    $composeFileMatches = $false
    foreach ($configFile in $configFiles.Split(",")) {
        if ($configFile.Trim() -ieq $expectedComposeFile) { $composeFileMatches = $true }
    }
    if ($containerName -cne "/$Name" -or -not $projectMatches -or
        $service -cne $ExpectedService -or
        $workingDirectory -ine $ExpectedRoot -or -not $composeFileMatches) {
        throw "Container $Name does not have the exact Atlas Compose identity; refusing to affect it."
    }

    $health = ""
    if ($container.State.Health) { $health = [string]$container.State.Health.Status }
    return @{
        name = $Name
        running = ([bool]$container.State.Running)
        health = $health
    }
}

Export-ModuleMember -Function ConvertFrom-AtlasContainerInspection
