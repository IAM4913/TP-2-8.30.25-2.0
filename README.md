# Truck Planner - Scheduling & Optimization Software

A comprehensive truck scheduling and optimization application built with FastAPI (backend) and React (frontend). This application helps optimize truck loading and routing based on customer requirements, weight constraints, and delivery priorities.

## Features

- **Excel Data Import**: Upload and parse Excel files with order data
- **Smart Optimization**: Automatically group orders by priority, zone, route, and customer
- **Weight Management**: Configurable weight limits for Texas vs other states
- **Customer Rules**: Support for no-multi-stop customers
- **Priority Handling**: Late orders, near-due orders, and within-window prioritization
- **Export Results**: Download optimized truck assignments as Excel files
- **Modern UI**: Clean, responsive React interface with real-time updates

## Architecture

### Backend (FastAPI)
- **FastAPI** web framework with automatic API documentation
- **Pandas** for Excel processing and data manipulation
- **Pydantic** for data validation and serialization
- **Uvicorn** ASGI server for development

### Frontend (React + TypeScript)
- **React 18** with TypeScript for type safety
- **Vite** for fast development and building
- **Tailwind CSS** for modern styling
- **Axios** for API communication
- **Lucide React** for icons

## Quick Start

### Prerequisites
- Python 3.8+
- Node.js 16+
- npm or yarn

### Backend Setup

1. Navigate to the backend directory:
```bash
cd backend
```

2. Run the development script (Windows):
```powershell
.\run_dev.ps1
```

Or manually:
```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run server
uvicorn app.main:app --host 127.0.0.1 --port 8010 --reload
```

The API will be available at `http://localhost:8010`
- API Documentation: `http://localhost:8010/docs`
- Health Check: `http://localhost:8010/health`

### Frontend Setup

1. Navigate to the frontend directory:
```bash
cd frontend
```

2. Run the development script (Windows):
```powershell
.\run_dev.ps1
```

Or manually:
```bash
# Install dependencies
npm install

# Start development server
npm run dev
```

The application will be available at `http://localhost:5173`

## Usage

1. **Upload Excel File**: Use the drag-and-drop interface to upload your truck planning Excel file
2. **Review Data**: Check the parsed data and ensure all required columns are mapped
3. **Configure Weights**: Adjust weight limits for Texas and other states if needed
4. **Optimize**: Click "Optimize Routes" to generate truck assignments
5. **Review Results**: View truck summaries and detailed order assignments
6. **Export**: Download the optimized results as an Excel file

## Required Excel Columns

Your input Excel file must contain these columns:
- `SO` - Sales Order Number
- `Line` - Line Number
- `Customer` - Customer Name
- `shipping_city` - Shipping City
- `shipping_state` - Shipping State
- `Ready Weight` - Total Weight
- `RPcs` - Number of Pieces
- `Grd` - Grade
- `Size` - Size Information
- `Width` - Width (for overwidth detection)
- `Earliest Due` - Earliest Due Date
- `Latest Due` - Latest Due Date

Optional columns for enhanced grouping:
- `Zone` - Geographic Zone
- `Route` - Route Information

## Configuration

### Weight Limits
Default weight configurations:
- **Texas**: 47,000 - 52,000 lbs
- **Other States**: 44,000 - 48,000 lbs

### No-Multi-Stop Customers
Certain customers cannot be combined with others on the same truck. This list is configurable in the backend.

## API Endpoints

- `GET /health` - Health check
- `POST /upload/preview` - Upload and preview Excel data
- `POST /optimize` - Generate optimized truck assignments
- `POST /export/trucks` - Export results to Excel
- `GET /no-multi-stop-customers` - Get list of restricted customers
- `POST /no-multi-stop-customers` - Update restricted customers list

## Development

### Project Structure
```
truck-planner/
├── backend/
│   ├── app/
│   │   ├── main.py          # FastAPI application
│   │   ├── schemas.py       # Pydantic models
│   │   ├── excel_utils.py   # Excel processing utilities
│   │   └── optimizer_simple.py # Optimization logic
│   ├── requirements.txt     # Python dependencies
│   └── run_dev.ps1         # Development script
├── frontend/
│   ├── src/
│   │   ├── components/     # React components
│   │   ├── api.ts         # API client
│   │   ├── types.ts       # TypeScript interfaces
│   │   └── App.tsx        # Main application
│   ├── package.json       # Node.js dependencies
│   └── run_dev.ps1       # Development script
└── README.md
```

### Adding New Features

1. **Backend**: Add new endpoints in `main.py`, update schemas in `schemas.py`
2. **Frontend**: Create new components in `src/components/`, update API client in `api.ts`
3. **Optimization**: Modify logic in `optimizer_simple.py`

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For questions or issues, please open a GitHub issue or contact the development team.