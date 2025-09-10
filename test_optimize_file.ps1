# Test the optimization endpoint with file upload
Write-Host "Testing optimization endpoint with file upload..."

$filePath = "Input Truck Planner.xlsx"
$uri = "http://127.0.0.1:8010/optimize"

try {
    Write-Host "Uploading file: $filePath"
    
    # Create multipart form data
    $boundary = [System.Guid]::NewGuid().ToString()
    $LF = "`r`n"
    
    $fileBytes = [System.IO.File]::ReadAllBytes($filePath)
    $fileName = [System.IO.Path]::GetFileName($filePath)
    
    $bodyLines = (
        "--$boundary",
        "Content-Disposition: form-data; name=`"file`"; filename=`"$fileName`"",
        "Content-Type: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet$LF",
        $LF
    ) -join $LF
    
    $bodyLines2 = (
        "$LF--$boundary",
        "Content-Disposition: form-data; name=`"planningWhse`"$LF",
        "ZAC",
        "--$boundary--$LF"
    ) -join $LF
    
    $bodyBytes = [System.Text.Encoding]::UTF8.GetBytes($bodyLines)
    $bodyBytes2 = [System.Text.Encoding]::UTF8.GetBytes($bodyLines2)
    
    $totalBytes = $bodyBytes + $fileBytes + $bodyBytes2
    
    $response = Invoke-WebRequest -Uri $uri -Method Post -Body $totalBytes -ContentType "multipart/form-data; boundary=$boundary"
    
    Write-Host "Success! Response:"
    $json = $response.Content | ConvertFrom-Json
    Write-Host "Number of trucks: $($json.trucks.Count)"
    Write-Host "Number of assignments: $($json.assignments.Count)"
    Write-Host "Sections: $($json.sections | ConvertTo-Json)"
    
    # Show first few trucks
    if ($json.trucks.Count -gt 0) {
        Write-Host "`nFirst few trucks:"
        $json.trucks[0..([Math]::Min(2, $json.trucks.Count - 1))] | ConvertTo-Json
    }
    
} catch {
    Write-Host "Error occurred: $($_.Exception.Message)"
    if ($_.ErrorDetails) {
        Write-Host "Error Details: $($_.ErrorDetails.Message)"
    }
}
