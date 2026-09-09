$ports = @(8000, 3001, 3000)

foreach ($port in $ports) {
  $connections = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
  foreach ($connection in $connections) {
    Stop-Process -Id $connection.OwningProcess -Force -ErrorAction SilentlyContinue
  }
}

Write-Host "Stopped local services listening on ports 8000, 3001, and 3000."
docker compose stop postgres
