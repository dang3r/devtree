# devtree

## Overview


## Running the Frontend (Development)

Requires Node.js 20+. If using nvm:

```bash
source ~/.nvm/nvm.sh && nvm use 20
cd frontend
npm run dev
```

The app will be available at http://localhost:3000

## Building and Serving Static Site

To build the static site for production:

```bash
source ~/.nvm/nvm.sh && nvm use 20
cd frontend
npm run build
```

This generates a static site in the `frontend/out/` directory.

To serve the static site locally:

```bash
npx serve out -p 3001
```

The static site will be available at http://localhost:3001

