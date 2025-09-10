# Truck Planner - Product Requirements Document (PRD)

## 1. Executive Summary

### 1.1 Product Overview
Truck Planner is a comprehensive logistics optimization system that automates the planning and scheduling of truck deliveries based on customer orders, weight constraints, delivery priorities, and routing requirements. The system processes Excel-based order data and generates optimized truck assignments while respecting complex business rules around customer combinations, state-specific weight limits, and delivery deadlines.

### 1.2 Business Value
- **Efficiency**: Reduces manual planning time from hours to minutes
- **Optimization**: Maximizes truck utilization while respecting weight and customer constraints
- **Compliance**: Ensures adherence to state-specific weight regulations (Texas vs. other states)
- **Priority Management**: Automatically handles late, near-due, and standard delivery windows
- **Cost Reduction**: Optimizes truck loading to minimize transportation costs
- **Audit Trail**: Provides detailed export reports for compliance and analysis

### 1.3 Target Users
- **Logistics Coordinators**: Primary users who upload data and run optimizations
- **Dispatch Managers**: Review and approve optimized truck assignments  
- **Operations Directors**: Monitor efficiency metrics and system performance
- **Drivers/Carriers**: Receive optimized load assignments via exported reports

## 2. Business Requirements

### 2.1 Core Business Rules

#### 2.1.1 Weight Configuration Rules
```yaml
Texas Shipments:
  Maximum Weight: 52,000 lbs (default, configurable 40,000-100,000)
  Minimum Weight: 47,000 lbs (default, configurable 40,000-100,000)
  Load Target: 98% of maximum weight for safety buffer

Out-of-State Shipments:  
  Maximum Weight: 48,000 lbs (default, configurable 40,000-100,000)
  Minimum Weight: 44,000 lbs (default, configurable 40,000-100,000)  
  Load Target: 98% of maximum weight for safety buffer
```

#### 2.1.2 Customer Combination Rules
**No-Multi-Stop Customers** (cannot be combined with other customers on same truck):
- Sabre Tubular Structures
- GamTex  
- Cmcr Fort Worth
- Ozark Steel LLC
- Gachman Metals & Recycling Co
- Sabre
- Sabre - Kennedale
- Sabre Industries
- Sabre Southbridge Plate STP
- Petrosmith Equipment LP
- W&W AFCO STEEL
- Red Dot Corporation

**Customer Combination Logic**:
- Same customer orders can always be combined
- Different customers can only be combined if BOTH allow multi-stop
- If either customer is in the no-multi-stop list, they get dedicated trucks

#### 2.1.3 Priority Bucket System
```yaml
Priority Levels:
  1. Late: Orders past their Latest Due date
  2. NearDue: Orders due within 3 days of current date
  3. WithinWindow: Orders due more than 3 days out
  4. NotDue: Orders with no due date or far future dates

Bucket Processing Rules:
  - Late trucks are processed first (highest priority)
  - Cross-bucket filling allowed with restrictions:
    * Late trucks can pull from NearDue/WithinWindow (but not items due after today)
    * NearDue trucks can pull from WithinWindow
    * Must match exact: Zone, Route, Customer, City, State
  - Same customer orders can span buckets on same truck
```

#### 2.1.4 Grouping and Routing Rules
```yaml
Primary Sort Order:
  1. Priority Rank (Late=0, NearDue=1, WithinWindow=2, NotDue=3)
  2. Zone (if available)
  3. Route (if available) 
  4. Customer Name
  5. Shipping State
  6. Shipping City

Truck Assignment Logic:
  - One customer per truck (unless multi-stop allowed)
  - Exact destination matching for cross-bucket fills
  - Orders split across multiple trucks if weight exceeds limits
  - Remainder processing for partial loads
```

#### 2.1.5 Planning Warehouse Filtering
- Default Planning Warehouse: "ZAC"
- Filter all input data to specified Planning Warehouse before optimization
- Configurable via UI, persisted in browser localStorage
- Case-insensitive matching on Planning Whse column

### 2.2 Data Processing Rules

#### 2.2.1 Required Input Data Columns
```yaml
Essential Columns:
  - SO: Sales Order Number
  - Line: Line Number  
  - Customer: Customer Name
  - shipping_city: Shipping City
  - shipping_state: Shipping State (used for TX vs other state weight limits)
  - Ready Weight: Total weight in pounds
  - RPcs: Ready Pieces (quantity)
  - Grd: Material Grade
  - Size: Material Size/Thickness
  - Width: Material Width (for overwidth detection >96")
  - Earliest Due: Earliest delivery date
  - Latest Due: Latest delivery date (used for Late calculation)

Optional Enhancement Columns:
  - Zone: Geographic zone for grouping
  - Route: Route identifier for grouping
  - Weight Per Piece: Calculated if missing (Ready Weight / RPcs)
  - Planning Whse: For warehouse filtering
  - shipping_address_1: Address details
  - BPcs: Total pieces (for DH Load List export)
  - Frm, TRTTAV No, R: Additional fields for export formats
```

#### 2.2.2 Calculated Fields
```yaml
Automatic Calculations:
  - Weight Per Piece: Ready Weight ÷ RPcs (if RPcs > 0)
  - Is Late: Latest Due < Current Date
  - Days Until Late: (Latest Due - Current Date) in days  
  - Is Overwidth: Width > 96 inches
  - Priority Bucket: Based on Latest Due vs Current Date + 3 days buffer
```

### 2.3 Optimization Algorithm Requirements

#### 2.3.1 Core Algorithm Steps
1. **Data Validation**: Ensure all required columns present
2. **Normalization**: Handle case variations in Zone/Route column names
3. **Priority Assignment**: Apply priority bucket logic
4. **Sorting**: Multi-level sort by priority → zone → route → customer → location
5. **Initial Grouping**: Group by zone/route/customer/destination  
6. **Truck Packing**: Fill trucks respecting weight limits and customer rules
7. **Remainder Processing**: Handle orders that exceed single truck capacity
8. **Cross-bucket Optimization**: Fill trucks across priority levels where allowed
9. **Final Assignment**: Generate truck summaries and line assignments

#### 2.3.2 Performance Requirements
- Process files up to 10,000 rows within 30 seconds
- Handle remainder processing with safety limit (100 iterations max)
- Memory efficient DataFrame operations
- Graceful error handling for invalid data

#### 2.3.3 Optimization Constraints
- Respect exact weight limits per state
- Never exceed customer combination rules
- Maintain order line integrity (no partial line splits without explicit remainder tracking)
- Preserve parent-child relationships for remainder orders
- Date validation for cross-bucket fills

## 3. Functional Requirements

### 3.1 File Upload and Preview
```yaml
File Upload:
  - Support: Excel .xlsx files only
  - Method: Drag-and-drop or file browser selection
  - Validation: Real-time column mapping validation
  - Preview: Show first 5 rows of data
  - Error Handling: Clear messages for invalid files/missing columns

Preview Response:
  - Headers: List of all column names from Excel
  - Row Count: Total number of data rows
  - Missing Required Columns: List of missing essential columns
  - Sample Data: First 5 rows for verification
```

### 3.2 Configuration Management
```yaml
Weight Configuration:
  - Texas Max/Min Weight: Input fields with validation (40,000-100,000 lbs)
  - Other States Max/Min Weight: Input fields with validation (40,000-100,000 lbs)  
  - Real-time UI updates
  - Persist settings during session

Planning Warehouse:
  - Text input field (default: "ZAC")
  - Case-insensitive
  - Persist in localStorage
  - Apply filter before optimization

Customer Rules Management:
  - View current no-multi-stop customer list
  - Add/remove customers from restriction list
  - Case-insensitive customer name matching
```

### 3.3 Optimization Engine
```yaml
Optimization Process:
  - Input: Excel file + weight config + planning warehouse filter
  - Processing: Multi-step algorithm with progress indication
  - Output: Truck summaries + detailed line assignments + section mapping
  - Error Handling: Detailed error messages for optimization failures
  - Performance: Real-time progress updates for large files

Algorithm Features:
  - Priority-based processing (Late → NearDue → WithinWindow)
  - Intelligent remainder handling for oversized orders  
  - Cross-bucket optimization with business rule enforcement
  - Zone/Route-aware grouping when data available
  - Customer combination rule enforcement
```

### 3.4 Results Display and Management
```yaml
Truck Summary View:
  - Truck Number, Customer, Destination (City, State)
  - Zone/Route (if available from input data)
  - Total Weight, Min/Max Weight, Utilization %
  - Total Orders, Lines, Pieces
  - Priority Bucket, Contains Late indicator
  - Max Width, Overwidth status
  - Color coding by utilization % (Red <84%, Yellow 84-90%, Green >90%)

Line Assignment View:  
  - Truck Number, SO, Line, Customer, Destination
  - Pieces on Transport, Total Ready Pieces, Weight per Piece
  - Total Weight, Width, Overwidth indicator
  - Late indicator, Earliest/Latest Due dates
  - Sortable and filterable columns

Interactive Features:
  - Multi-select lines across trucks
  - Combine selected lines into single truck
  - Real-time weight validation during combinations
  - Drag-and-drop line movement between trucks (future enhancement)
```

### 3.5 Export Capabilities
```yaml
Standard Excel Export:
  - Multi-sheet workbook (Truck Summary + Order Details)
  - Formatted tables with headers
  - Downloadable .xlsx file
  - Filename: truck_optimization_results.xlsx

DH Load List Export:
  - Specialized format for carrier integration
  - Multi-sheet by priority (Late+NearDue, WithinWindow)  
  - Load separator rows with utilization stats
  - Color-coded utilization percentages
  - Date formatting (mm/dd/yyyy)
  - Hidden columns for layout compatibility
  - Auto-fit column widths
  - Filename: dh_load_list.xlsx

Export Features:
  - Apply same Planning Warehouse filter as optimization
  - Include all calculated fields and assignments
  - Preserve formatting and data types
  - Error handling for large exports
```

## 4. Technical Requirements

### 4.1 Backend Architecture
```yaml
Framework: FastAPI 0.115.0+
  - Automatic API documentation via OpenAPI/Swagger
  - Type validation with Pydantic 2.8+
  - Async request handling
  - CORS middleware for frontend integration

Core Dependencies:
  - uvicorn[standard]==0.30.6 (ASGI server)
  - pandas==2.2.2 (data processing)
  - openpyxl==3.1.5 (Excel file handling)
  - python-multipart==0.0.9 (file uploads)
  - psycopg[binary]==3.2.9 (PostgreSQL/Supabase)
  - python-dotenv==1.0.1 (environment configuration)

Performance Requirements:
  - Handle files up to 10,000 rows
  - Response time <30s for optimization
  - Memory efficient processing
  - Graceful error handling and logging
```

### 4.2 Frontend Architecture  
```yaml
Framework: React 18 + TypeScript
  - Type-safe development
  - Component-based architecture
  - React Router for navigation
  - Modern hooks-based patterns

Build Tools:
  - Vite 5.4+ (fast development and building)
  - TypeScript 5.5+ (type checking)
  - Tailwind CSS 3.3+ (utility-first styling)

Core Libraries:
  - axios 1.5+ (API communication)
  - react-dropzone 14.2+ (file upload UI)
  - lucide-react 0.263+ (modern icons)
  - react-router-dom 6.15+ (routing)

UI Requirements:
  - Responsive design (mobile-friendly)
  - Modern, clean interface
  - Real-time feedback and loading states
  - Accessible components
  - Cross-browser compatibility
```

### 4.3 Database Integration
```yaml
Database: Supabase (PostgreSQL)
  - Connection via environment variables
  - SSL required for security
  - Connection pooling and timeouts
  - Health check endpoint (/db/ping)

Environment Configuration:
  - SUPABASE_DB_URL (full connection string)
  - Alternative: SUPABASE_DB_HOST, SUPABASE_DB_USER, SUPABASE_DB_PASSWORD, etc.
  - URL encoding for special characters
  - Graceful fallback if DB unavailable

Future Database Features:
  - Store optimization history
  - User preferences and settings
  - Customer rule management
  - Performance analytics
```

### 4.4 API Design
```yaml
REST API Endpoints:

Health and System:
  GET /health - System health check
  GET /db/ping - Database connectivity test

Data Processing:
  POST /upload/preview - Upload and preview Excel file
  POST /optimize - Generate optimized truck assignments
  
Export Operations:
  POST /export/trucks - Export standard Excel format
  POST /export/dh-load-list - Export DH Load List format
  
Configuration Management:
  GET /no-multi-stop-customers - Get restricted customers list
  POST /no-multi-stop-customers - Update restricted customers list
  
Operations:
  POST /combine-trucks - Combine selected lines into single truck

Request/Response Format:
  - JSON for all API communication
  - Pydantic models for validation
  - Comprehensive error responses
  - File uploads via multipart/form-data
```

## 5. User Experience Requirements

### 5.1 User Interface Design
```yaml
Design System:
  - Color Palette: Blue primary (#3B82F6), gray neutrals, semantic colors
  - Typography: Modern, readable font stack
  - Icons: Lucide React icon set for consistency  
  - Spacing: Consistent spacing scale (Tailwind CSS)
  - Components: Reusable, accessible UI components

Layout Structure:
  - Header: Navigation and branding
  - Sidebar: Multi-step workflow navigation
  - Main Content: Context-sensitive views
  - Footer: Status and system information

Navigation Flow:
  1. Upload → File selection and preview
  2. Configure → Weight settings and planning warehouse  
  3. Optimize → Run optimization with progress feedback
  4. Results → Review and manage truck assignments
  5. Export → Download formatted reports
```

### 5.2 Workflow Requirements
```yaml
Primary User Journey:
  1. File Upload:
     - Drag-and-drop or browse for Excel file
     - Real-time validation feedback
     - Preview parsed data and column mapping
     - Clear error messages for invalid files
  
  2. Configuration:
     - Review and adjust weight limits by state
     - Set planning warehouse filter
     - View current customer restriction rules
     - Save preferences for session
  
  3. Optimization:
     - One-click optimization with progress indicator
     - Clear success/error messaging
     - Automatic navigation to results
     - Performance metrics display
  
  4. Results Review:
     - Tabbed interface (Truck Summary, Line Details)
     - Interactive filtering and sorting
     - Visual indicators for status and utilization
     - Multi-select for truck combination operations
  
  5. Export:
     - Multiple export format options
     - One-click download with progress indication
     - Format-appropriate filename generation
     - Export confirmation and success messaging

Error Handling:
  - Graceful degradation for missing optional data
  - Clear, actionable error messages
  - Retry mechanisms for transient failures
  - Help text and tooltips for complex operations
```

### 5.3 Performance and Usability
```yaml
Performance Targets:
  - Initial page load: <3 seconds
  - File upload preview: <5 seconds for 1000 rows
  - Optimization processing: <30 seconds for 10,000 rows
  - Export generation: <15 seconds for complex formats
  - UI responsiveness: <100ms for interactions

Usability Features:
  - Auto-save user preferences
  - Undo/redo for truck combinations (future)
  - Keyboard shortcuts for power users
  - Bulk operations for efficiency
  - Progress indicators for long operations
  - Context-sensitive help and tooltips
```

## 6. Data Requirements

### 6.1 Input Data Schema
```yaml
Required Fields:
  SO: string (Sales Order Number, unique identifier)
  Line: string (Line Number, unique within SO)
  Customer: string (Customer Name, used for grouping and restrictions)
  shipping_city: string (Destination city)
  shipping_state: string (State code, determines weight limits)
  Ready Weight: number (Total weight in pounds, >0)
  RPcs: number (Ready pieces count, >0)
  Grd: string (Material grade)
  Size: string/number (Material size or thickness)
  Width: number (Width in inches, for overwidth detection)
  Earliest Due: date (Earliest acceptable delivery date)
  Latest Due: date (Latest acceptable delivery date, used for priority)

Optional Fields:
  Zone: string (Geographic zone for enhanced grouping)
  Route: string (Route identifier for enhanced grouping)
  Weight Per Piece: number (Calculated if not provided)
  Planning Whse: string (Warehouse filter, default ZAC)
  shipping_address_1: string (Full shipping address)
  BPcs: number (Total pieces for DH export)
  Frm, TRTTAV No, R: various (Additional fields for specialized exports)

Data Validation Rules:
  - All required fields must be non-null
  - Numeric fields must be valid numbers >0
  - Dates must be valid date format
  - State codes should be standard 2-letter codes
  - Customer names matched case-insensitively against restrictions
```

### 6.2 Output Data Schema
```yaml
Truck Summary:
  truckNumber: integer (Sequential truck identifier)
  customerName: string (Primary customer on truck)
  customerAddress: string (optional, shipping address)
  customerCity: string (Destination city)
  customerState: string (Destination state)
  zone: string (optional, from input data)
  route: string (optional, from input data)
  totalWeight: number (Sum of all line weights on truck)
  minWeight: integer (State-based minimum weight limit)
  maxWeight: integer (State-based maximum weight limit)
  totalOrders: integer (Unique SO count on truck)
  totalLines: integer (Total line count on truck)
  totalPieces: integer (Sum of all pieces on truck)
  maxWidth: number (Maximum width of any line on truck)
  percentOverwidth: number (Percentage of overwidth lines)
  containsLate: boolean (True if any line is late)
  priorityBucket: string (Late, NearDue, WithinWindow, or NotDue)

Line Assignment:
  truckNumber: integer (References truck summary)
  so: string (Sales order number)
  line: string (Line number, may include remainder suffix)
  customerName: string (Customer name)
  customerAddress: string (optional)
  customerCity: string (Destination city)  
  customerState: string (Destination state)
  piecesOnTransport: integer (Pieces assigned to this truck)
  totalReadyPieces: integer (Total pieces for this line)
  weightPerPiece: number (Calculated or input weight per piece)
  totalWeight: number (Total weight for pieces on this truck)
  width: number (Width in inches)
  isOverwidth: boolean (True if width > 96)
  isLate: boolean (True if past latest due date)
  earliestDue: date (optional, earliest due date)
  latestDue: date (optional, latest due date)
  isPartial: boolean (True if line split across trucks)
  isRemainder: boolean (True if this is a remainder portion)
  parentLine: string (optional, reference to parent line for remainders)
  remainingPieces: integer (Pieces not yet assigned)
```

## 7. Integration Requirements

### 7.1 External System Integration
```yaml
Current Integrations:
  - Excel Files: Primary data import mechanism
  - Supabase Database: Optional persistence and configuration storage
  - Browser localStorage: User preference persistence

Future Integration Opportunities:
  - ERP Systems: Direct API integration for order data
  - TMS (Transportation Management Systems): Export optimized routes
  - Carrier APIs: Real-time capacity and pricing
  - GPS Tracking: Real-time delivery status
  - Email Systems: Automated report distribution
  - BI Tools: Analytics and reporting dashboard
```

### 7.2 Export Format Requirements
```yaml
Standard Excel Export:
  - Multi-sheet workbook (.xlsx format)
  - Sheet 1: Truck Summary (all truck metadata)
  - Sheet 2: Order Details (all line assignments)
  - Professional formatting with headers
  - Numeric formatting for weights and percentages
  - Date formatting for due dates

DH Load List Export:
  - Carrier-specific format for Jordan Carriers integration
  - Multi-sheet by priority bucket
  - Load separator rows with utilization statistics
  - Color-coded utilization percentages (Red/Yellow/Green)
  - Hidden columns for layout compatibility
  - Auto-fit column widths
  - Specific date format (mm/dd/yyyy)
  - Italian formatting and professional styling

API Export Options:
  - JSON format for programmatic integration
  - CSV format for simple data exchange
  - PDF format for printed reports (future)
  - XML format for legacy system integration (future)
```

## 8. Security and Compliance Requirements

### 8.1 Data Security
```yaml
Data Protection:
  - No persistent storage of customer data in local system
  - Secure file upload with validation
  - Input sanitization and validation
  - SQL injection prevention via parameterized queries
  - XSS protection via proper encoding

Network Security:
  - HTTPS required for all production deployments
  - CORS configuration for frontend integration
  - SSL/TLS for database connections
  - Environment variable protection for credentials
  - No sensitive data in logs or error messages
```

### 8.2 Privacy and Compliance
```yaml
Data Handling:
  - Customer data processed in memory only
  - No long-term storage of business data
  - User preferences stored locally (browser localStorage)
  - Database used only for configuration and system data
  - Secure data transmission between frontend/backend

Compliance Considerations:
  - SOC 2 Type II compliance for SaaS deployment
  - GDPR compliance for EU customer data
  - Transportation regulation compliance (DOT, etc.)
  - Industry-specific compliance (logistics/transportation)
```

## 9. Deployment and Operations

### 9.1 Development Environment
```yaml
Backend Development:
  - Python 3.11+ virtual environment
  - FastAPI development server with hot reload
  - Environment variables via .env file
  - Local PostgreSQL or Supabase development instance
  - PowerShell automation scripts for Windows

Frontend Development:
  - Node.js 16+ with npm/yarn
  - Vite development server with HMR
  - TypeScript compilation
  - Tailwind CSS JIT compilation
  - Local development proxy to backend

Development Tools:
  - VS Code with Python and TypeScript extensions
  - Git version control
  - ESLint and Prettier for code formatting
  - pytest for backend testing
  - Vitest for frontend testing
```

### 9.2 Production Deployment (AWS)
```yaml
Infrastructure:
  - AWS ECS or Lambda for backend APIs
  - AWS S3 + CloudFront for frontend static files
  - AWS RDS PostgreSQL or Supabase for database
  - AWS ALB for load balancing and SSL termination
  - AWS Route 53 for DNS management

CI/CD Pipeline:
  - GitHub Actions for automated testing and deployment
  - Docker containers for consistent deployment
  - Automated testing on pull requests
  - Blue-green deployment for zero downtime
  - Infrastructure as Code (CDK/CloudFormation)

Monitoring and Observability:
  - AWS CloudWatch for logs and metrics
  - Application performance monitoring (APM)
  - Error tracking and alerting
  - User analytics and usage metrics
  - Health checks and uptime monitoring
```

### 9.3 Scalability Requirements
```yaml
Performance Targets:
  - Support 100+ concurrent users
  - Process files up to 50,000 rows
  - Sub-30 second optimization for large datasets
  - 99.9% uptime SLA
  - Auto-scaling based on demand

Resource Requirements:
  - Backend: 2+ CPU cores, 4GB+ RAM for optimization workloads
  - Database: Managed PostgreSQL with connection pooling
  - Frontend: CDN distribution for global performance
  - Storage: Temporary file processing with automatic cleanup
```

## 10. Success Metrics and KPIs

### 10.1 Business Metrics
```yaml
Efficiency Metrics:
  - Average planning time reduction (target: 80% reduction)
  - Truck utilization improvement (target: >85% average)
  - Cost savings per optimization (fuel, labor, equipment)
  - On-time delivery improvement
  - Manual planning error reduction

User Adoption:
  - Daily active users
  - Files processed per day/week/month
  - User retention rate
  - Feature utilization rates
  - User satisfaction scores
```

### 10.2 Technical Metrics
```yaml
Performance KPIs:
  - Average optimization processing time
  - File upload success rate
  - API response time percentiles (P95, P99)
  - Error rates and types
  - System uptime and availability

Quality Metrics:
  - Optimization accuracy (manual validation)
  - Customer constraint compliance (100% target)
  - Weight limit compliance (100% target)
  - Export format accuracy
  - Data integrity maintenance
```

## 11. Risk Management

### 11.1 Technical Risks
```yaml
High Risk:
  - Complex optimization algorithm performance degradation
  - Excel file format variations and compatibility issues
  - Database connection failures affecting operations
  - Memory usage spikes for large datasets

Mitigation Strategies:
  - Algorithm performance testing and optimization
  - Comprehensive Excel format testing
  - Database failover and connection pooling
  - Memory monitoring and optimization
  - Graceful degradation for system failures
```

### 11.2 Business Risks
```yaml
High Risk:
  - Incorrect optimization results leading to delivery failures
  - Customer data privacy breaches
  - Regulatory compliance violations
  - System unavailability during critical planning periods

Mitigation Strategies:
  - Comprehensive testing of business rules and edge cases
  - Security audit and penetration testing
  - Compliance review and documentation
  - High availability deployment architecture
  - Regular backup and disaster recovery testing
```

## 12. Future Roadmap

### 12.1 Phase 2 Enhancements
```yaml
Advanced Features:
  - Machine learning optimization suggestions
  - Real-time route optimization with GPS data
  - Advanced analytics and reporting dashboard
  - Multi-tenant support for different organizations
  - Mobile app for drivers and dispatchers

Integration Expansions:
  - Direct ERP system integration (SAP, Oracle, etc.)
  - TMS integration for end-to-end logistics
  - Carrier API integration for capacity and pricing
  - Email automation for report distribution
  - Slack/Teams integration for notifications
```

### 12.2 Phase 3 Vision
```yaml
Strategic Evolution:
  - AI-powered demand forecasting and planning
  - IoT integration for real-time asset tracking
  - Blockchain integration for supply chain transparency
  - Advanced simulation and scenario planning
  - White-label solution for logistics providers

Platform Expansion:
  - Multi-modal transportation optimization
  - International shipping compliance
  - Carbon footprint optimization
  - Dynamic routing based on traffic and conditions
  - Advanced constraint programming algorithms
```

---

## Appendix A: Business Rule Examples

### Weight Limit Validation Example
```yaml
Input Order:
  Customer: "ABC Steel Corp"
  Shipping State: "TX"  
  Ready Weight: 55000 lbs

Processing:
  1. Identify state: Texas (TX)
  2. Apply Texas weight limits: Max 52,000 lbs
  3. Order exceeds single truck capacity
  4. Split into multiple trucks:
     - Truck 1: 52,000 lbs (full capacity)
     - Truck 2: 3,000 lbs (remainder)
  5. Mark remainder with parent line reference
```

### Customer Combination Example
```yaml
Scenario: Two orders for different customers
Order A: Customer "Sabre Industries" (no-multi-stop customer)
Order B: Customer "Regular Customer Inc"

Processing:
  1. Check no-multi-stop list
  2. "Sabre Industries" found in restricted list
  3. Cannot combine with any other customer
  4. Assign to dedicated truck
  5. "Regular Customer Inc" assigned separately
```

### Priority Bucket Example
```yaml
Current Date: 2025-09-07
Orders:
  Order 1: Latest Due = 2025-09-05 → Late (past due)
  Order 2: Latest Due = 2025-09-09 → NearDue (2 days out)  
  Order 3: Latest Due = 2025-09-15 → WithinWindow (8 days out)

Processing Order:
  1. Late orders processed first
  2. NearDue orders processed second
  3. WithinWindow orders processed last
  4. Cross-bucket filling allowed with restrictions
```

## Appendix B: API Documentation Examples

### Upload Preview API
```yaml
POST /upload/preview
Content-Type: multipart/form-data
Request: Excel file upload

Response:
{
  "headers": ["SO", "Line", "Customer", "shipping_city", ...],
  "rowCount": 1542,
  "missingRequiredColumns": ["Width"], 
  "sample": [
    {"SO": "12345", "Line": "001", "Customer": "ABC Corp", ...},
    ...
  ]
}
```

### Optimization API  
```yaml
POST /optimize
Content-Type: multipart/form-data
Request: 
  - file: Excel file
  - planningWhse: "ZAC" (optional)

Response:
{
  "trucks": [
    {
      "truckNumber": 1,
      "customerName": "ABC Corp",
      "totalWeight": 51500,
      "maxWeight": 52000,
      "containsLate": false,
      ...
    }
  ],
  "assignments": [
    {
      "truckNumber": 1,
      "so": "12345", 
      "line": "001",
      "totalWeight": 2500,
      "isLate": false,
      ...
    }
  ],
  "sections": {
    "Late": [1, 5, 8],
    "WithinWindow": [2, 3, 4, 6, 7]
  }
}
```

This PRD provides comprehensive documentation for rebuilding the Truck Planner system while preserving all business logic, user experience, and technical requirements. It serves as both a specification for new development and a reference for system maintenance and enhancement.
