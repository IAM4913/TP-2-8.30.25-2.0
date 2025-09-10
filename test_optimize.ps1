# Quick test script for the optimization endpoint
Write-Host "Testing optimization endpoint..."

# Create a simple test payload with minimal data
$testData = @{
    data = @(
        @{
            "Ship Date" = "2025-01-30"
            Customer = "Test Customer"
            Type = "Material"
            SO = "SO001"
            Line = "1"
            R = ""
            "Planning Whse" = "TX"
            Zone = "1"
            Route = "A"
            BPcs = 10
            RPcs = 10
            "Balance Weight" = 1000
            "Ready Weight" = 1000
            Frm = ""
            Grd = ""
            Size = "12x4"
            Width = 12
            Lgth = 20
            trttav_no = ""
            trttav_itm = ""
            Prv = ""
            PWh = ""
            "Lst Prs" = ""
            Other = ""
            ISP = ""
            "Partial Ship" = ""
            Credit = ""
            Pull = ""
            shipping_zip = "75001"
            "Earliest Due" = "2025-01-30"
            "Latest Due" = "2025-02-05"
            shipping_address_1 = "123 Test St"
            shipping_address_2 = ""
            shipping_city = "Dallas"
            shipping_state = "TX"
            ship_hold = ""
            "Weight Per Piece" = 100
            "Is Late" = $false
            "Days Until Late" = 5
            "Is Overwidth" = $false
        }
    )
} | ConvertTo-Json -Depth 3

try {
    Write-Host "Sending optimization request..."
    $response = Invoke-WebRequest -Uri "http://127.0.0.1:8010/optimize" -Method POST -Body $testData -ContentType "application/json"
    Write-Host "Response Status: $($response.StatusCode)"
    Write-Host "Response Content:"
    $response.Content | ConvertFrom-Json | ConvertTo-Json -Depth 10
} catch {
    Write-Host "Error occurred: $($_.Exception.Message)"
    Write-Host "Response: $($_.Exception.Response)"
    if ($_.Exception.Response) {
        $reader = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream())
        Write-Host "Error Details: $($reader.ReadToEnd())"
    }
}
