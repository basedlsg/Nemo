# Geo-Adaptive Energy Assistant - Explorer UI

A minimal Next.js frontend for the Chinese energy regulation compliance assistant.

## Features

- **Bilingual Interface**: Chinese-first with English support
- **Province Selection**: Guangdong, Shandong, Inner Mongolia
- **Asset Type Filtering**: Solar, Wind, Battery Storage, Coal Flexibility
- **Document Class Selection**: Grid Connection, Market Rules, Dispatch Operations
- **Real-time Query**: Direct integration with API gateway
- **Citation Display**: Shows official document sources with effective dates
- **Error Handling**: Structured refusal messages with policy information

## Quick Start

```bash
# Install dependencies
npm install

# Set up environment
cp .env.local.example .env.local
# Edit .env.local with your API gateway URL

# Run development server
npm run dev

# Build for production
npm run build
npm start
```

## Environment Variables

- `API_GATEWAY_URL`: URL of the API gateway service (default: http://localhost:8000)

## Usage

1. Select province, document class, and asset type
2. Enter your question in Chinese (recommended) or English
3. Click "查询" (Query) or press Ctrl+Enter
4. View results with official citations
5. Handle refusals with clear policy explanations

## API Integration

The UI integrates with the API gateway at `/api/v1/query` endpoint:

```typescript
POST /api/v1/query
{
  "province": "guangdong",
  "doc_class": "grid_connection", 
  "asset": "solar",
  "question": "光伏电站并网需要什么资料？",
  "lang": "zh"
}
```

## Styling

- Uses system fonts with Noto Sans SC for Chinese text
- Responsive design with CSS Grid
- Clean, minimal interface focused on functionality
- Proper Chinese text rendering with line-break handling

## Acceptance Criteria

- ✅ Works against API gateway in staging
- ✅ Chinese text renders cleanly with proper fonts
- ✅ Shows refusal banner using standardized JSON format
- ✅ Bilingual support (Chinese primary, English secondary)
- ✅ Responsive design for desktop and mobile
- ✅ Keyboard shortcuts (Ctrl+Enter to submit)
- ✅ Loading states and error handling