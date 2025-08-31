# Product Requirements Document
## Truck Scheduling & Optimization Software

**Version:** 1.0  
**Date:** August 30, 2025  
**Status:** Draft

---

## 1. Executive Summary

### 1.1 Purpose
This document outlines the requirements for a truck scheduling and optimization software system designed to automate and optimize the planning of freight transportation. The system will group orders efficiently based on customer, location, weight constraints, and delivery windows while maximizing truck utilization and prioritizing late shipments.

### 1.2 Scope
The software will handle order import, automatic route optimization, manual adjustment capabilities, and export functionality for finalized transportation plans.

### 1.3 Key Benefits
- Automated optimization of truck loads based on multiple constraints
- Prioritization of late orders to minimize delivery delays
- Maximization of truck utilization to reduce transportation costs
- Clear visibility into load composition and delivery status
- Flexibility for manual adjustments when needed

---

## 2. Functional Requirements

### 2.1 Data Import Module

#### 2.1.1 File Import Capability
- **Supported Format:** Excel (.xlsx) files
- **Import Method:** File upload interface with drag-and-drop capability
- **Validation:** System shall validate file format and required fields before processing

#### 2.1.2 Required Import Fields
The system must import and process the following mandatory fields:
- **Sales Order Number (SO)** - Unique identifier for each sales order
- **Line Number** - Line item identifier within the sales order
- **Customer Name** - Name of the customer receiving the shipment
- **Shipping City** - Destination city for delivery
- **Shipping State** - Destination state for delivery
- **Ready Weight (lbs)** - Weight of items ready for shipment
- **Ready Pieces (quantity)** - Number of pieces ready for shipment
- **Material Grade** - Grade specification of the material
- **Material Thickness (Size)** - Thickness dimension of the material
- **Material Width** - Width dimension of the material in inches
- **Earliest Ship Date** - First allowable date for shipment
- **Latest Ship Date** - Last acceptable date before shipment is considered late

#### 2.1.3 Calculated Fields
The system shall automatically calculate:
- **Ready Weight per Piece** = Ready Weight ÷ Ready Pieces
- **Late Status** = Current Date > Latest Ship Date
- **Overwidth Status** = Material Width > 96 inches
- **Days Until Late** = Latest Ship Date - Current Date

### 2.2 Optimization Engine

#### 2.2.1 Grouping Logic

##### Primary Grouping Rules
1. **Customer Isolation:** Never mix different customers on the same truck
2. **Location Consistency:** Group only orders going to the same city and state
3. **Sales Order Integrity:** Attempt to keep sales order lines together when possible
4. **Line Splitting:** Allow splitting of order lines when necessary to optimize loads
   - Track remaining pieces when lines are split
   - Maintain visibility of partial shipments

##### Date-Based Prioritization
1. **Priority 1 - Late Orders:** Orders past their Latest Ship Date
2. **Priority 2 - Near Due:** Orders within 3 days of Latest Ship Date
3. **Priority 3 - Within Window:** Orders between Earliest and Latest Ship Date
4. **Priority 4 - Not Due:** Orders before Earliest Ship Date

##### Material Width Optimization
- **Overwidth Classification:** Materials > 96" width
- **Overwidth Grouping:** Combine overwidth materials to maximize truck weight
- **Mixed Loading:** Fill remaining capacity with legal width materials when possible

#### 2.2.2 Weight Constraints

##### Texas Shipments
- **Maximum Weight:** 52,000 lbs
- **Minimum Weight:** 47,000 lbs
- **Target Utilization:** 90-100% of maximum

##### Out-of-State Shipments
- **Maximum Weight:** 48,000 lbs
- **Minimum Weight:** 44,000 lbs
- **Target Utilization:** 90-100% of maximum

##### Customization Options
- Allow adjustment in 1,000 lb increments
- Minimum floor: 40,000 lbs
- Constraint: Maximum weight must exceed minimum weight

#### 2.2.3 Load Quality Grading
Assign quality grades to optimized loads based on:
- **Grade A - Optimal Load:**
  - ≥90% truck utilization
  - Within delivery window
  - Single customer
  - Single sales order
  - Single line item
  - No partial shipments
- **Grade B - Good Load:**
  - ≥85% truck utilization
  - Within delivery window
  - Single customer
  - Multiple sales orders or lines allowed
- **Grade C - Acceptable Load:**
  - ≥80% truck utilization
  - Mixed delivery windows
  - Contains late materials
- **Grade D - Suboptimal Load:**
  - <80% truck utilization
  - Requires manual review

### 2.3 User Interface Requirements

#### 2.3.1 Data Upload Screen
- **File Selection:** Browse or drag-and-drop interface
- **Upload Progress:** Visual progress indicator
- **Validation Results:** Display of validation errors or success message
- **Field Mapping:** Option to map custom column names to required fields

#### 2.3.2 Data Summary Dashboard

##### Overview Statistics Panel
Display aggregated metrics for uploaded data:
- **By Customer:**
  - Customer Name
  - Customer City
  - Total Weight
  - Late Weight (orders past due)
  - Delivery Window Weight (orders within window)
  - Not Due Weight (orders before earliest ship date)
  
##### Weight Configuration Panel
- **Display current weight limits** for in-state and out-of-state
- **Adjustment controls** with 1,000 lb increment selectors
- **Validation** to ensure max > min weight
- **"Optimize Routes" button** to trigger optimization process

#### 2.3.3 Truck Summary View

##### Table Structure
Display optimized truck loads with the following columns:
1. **Truck Number** - Sequential identifier starting from 1
2. **Customer Name** - Destination customer
3. **Customer Address** - Full delivery address
4. **Customer City** - Delivery city
5. **Customer State** - Delivery state
6. **Total Weight** - Sum of all items on truck
7. **Min Weight** - Minimum weight threshold
8. **Max Weight** - Maximum weight threshold
9. **Total Orders** - Count of unique sales orders
10. **Total Lines** - Count of order lines
11. **Total Pieces** - Sum of all pieces
12. **Max Width** - Widest material dimension on truck
13. **% Overwidth** - Percentage of load that is overwidth
14. **Contains Late** - Boolean indicator for late orders

##### View Organization
Organize trucks into three sections:
1. **Section 1 - Late Orders:** Trucks containing orders past Latest Ship Date
2. **Section 2 - Near Due:** Trucks with orders within 3 days of Latest Ship Date
3. **Section 3 - Within Window:** Trucks with orders in normal delivery window

##### Interactive Features
- **Drill-through capability** to view load details
- **Multi-select functionality** for batch operations
- **Export selected trucks** to specified format
- **Manual adjustment** options for load composition

#### 2.3.4 Order Detail View

##### Detailed Order Information
For each truck load, display:
1. **Truck Number** - Assigned truck identifier
2. **Sales Order** - SO number
3. **Sales Order Line** - Line item number
4. **Customer Name** - Receiving customer
5. **Customer Address** - Full delivery address
6. **Customer City** - Destination city
7. **Customer State** - Destination state
8. **Pieces on Transport** - Number of pieces on this truck
9. **Total Ready Pieces** - Total pieces available for order line
10. **Weight per Piece** - Calculated weight per unit
11. **Total Weight** - Total weight for this line on truck

### 2.4 Export Functionality

#### 2.4.1 Export Formats
- **Excel (.xlsx)** - Primary export format
- **CSV** - Alternative format for system integration
- **PDF** - Formatted reports for printing

#### 2.4.2 Export Options
- **Single truck export** - Export individual truck manifest
- **Batch export** - Export multiple selected trucks
- **Full export** - Export all optimized routes
- **Custom templates** - Support for predefined export templates

---

## 3. Non-Functional Requirements

### 3.1 Performance Requirements
- **Import Processing:** Handle files up to 50,000 rows within 30 seconds
- **Optimization Speed:** Complete route optimization within 60 seconds for up to 1,000 orders
- **UI Responsiveness:** Page load times under 2 seconds
- **Concurrent Users:** Support minimum 50 concurrent users

### 3.2 Usability Requirements
- **Browser Compatibility:** Support latest versions of Chrome, Firefox, Safari, Edge
- **Responsive Design:** Functional on desktop and tablet devices
- **Accessibility:** WCAG 2.1 Level AA compliance
- **Help Documentation:** In-app help tooltips and user guide

### 3.3 Data Requirements
- **Data Retention:** Maintain import history for 90 days
- **Audit Trail:** Log all optimization runs and manual adjustments
- **Data Security:** Encrypt sensitive customer information
- **Backup:** Daily automated backups with 30-day retention

### 3.4 Integration Requirements
- **API Availability:** RESTful API for external system integration
- **Authentication:** Support for SSO and standard username/password
- **Data Exchange:** Support for automated data import via API or FTP

---

## 4. Business Rules

### 4.1 Optimization Priorities
1. Minimize late shipments
2. Maximize truck utilization
3. Minimize number of trucks required
4. Keep sales orders together when possible
5. Group overwidth materials efficiently

### 4.2 Constraint Hierarchy
1. Never exceed maximum weight limits
2. Never mix customers on same truck
3. Never mix destination cities/states
4. Prioritize late orders
5. Maintain minimum weight thresholds when possible

### 4.3 Manual Override Rules
- Users can manually adjust automated assignments
- System must recalculate metrics after manual changes
- Manual changes must be logged with user and timestamp
- Warning messages for constraint violations

---

## 5. User Stories

### 5.1 Import and Analysis
**As a** logistics planner  
**I want to** import order data from Excel  
**So that** I can quickly analyze shipping requirements

### 5.2 Automated Optimization
**As a** logistics manager  
**I want to** automatically optimize truck loads  
**So that** I can minimize transportation costs and late deliveries

### 5.3 Manual Adjustments
**As a** shipping coordinator  
**I want to** manually adjust optimized loads  
**So that** I can accommodate special customer requirements

### 5.4 Export and Execution
**As a** dispatch operator  
**I want to** export finalized truck manifests  
**So that** I can provide drivers with accurate load information

---

## 6. Acceptance Criteria

### 6.1 Import Functionality
- ✓ System successfully imports Excel files with all required fields
- ✓ Validation errors are clearly displayed
- ✓ Calculated fields are computed correctly

### 6.2 Optimization Engine
- ✓ No customer mixing occurs in optimized loads
- ✓ Weight constraints are respected
- ✓ Late orders are prioritized appropriately
- ✓ Truck utilization meets target thresholds

### 6.3 User Interface
- ✓ All specified views are implemented and functional
- ✓ Drill-through navigation works correctly
- ✓ Export functionality produces accurate output

### 6.4 Performance
- ✓ Optimization completes within specified time limits
- ✓ System handles concurrent users without degradation
- ✓ UI remains responsive during processing

---

## 7. Technical Architecture (Recommended)

### 7.1 Technology Stack
- **Frontend:** React.js or Vue.js for responsive UI
- **Backend:** Node.js or Python (FastAPI/Django)
- **Database:** PostgreSQL for data persistence
- **Optimization Engine:** OR-Tools or custom algorithm
- **File Processing:** Apache POI or openpyxl

### 7.2 Deployment
- **Cloud Platform:** AWS, Azure, or Google Cloud
- **Containerization:** Docker for consistent deployment
- **CI/CD:** Automated testing and deployment pipeline

---

## 8. Future Enhancements

### 8.1 Phase 2 Features
- Real-time GPS tracking integration
- Route optimization with distance calculations
- Driver mobile app for updates
- Customer notification system
- Historical performance analytics

### 8.2 Phase 3 Features
- Machine learning for demand prediction
- Automatic carrier selection
- Cost optimization modeling
- Integration with ERP systems
- Multi-modal transportation support

---

## 9. Appendices

### Appendix A: Glossary
- **SO:** Sales Order
- **Latest Ship Date:** Customer's required delivery date
- **Overwidth:** Material exceeding 96 inches in width
- **Truck Utilization:** Percentage of maximum weight capacity used

### Appendix B: Sample Data Format
Reference the attached Excel file "Input Truck Planner.xlsx" for expected data structure

### Appendix C: Export Format Specification
Detailed specifications for export formats to be defined during technical design phase