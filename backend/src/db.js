const { Pool } = require('pg');

// PostgreSQL connection pool configuration
const pool = new Pool({
  connectionString: process.env.DATABASE_URL,
  max: 20, // Maximum number of clients in the pool
  idleTimeoutMillis: 30000, // Close idle clients after 30 seconds
  connectionTimeoutMillis: 2000, // Return error after 2 seconds if can't connect
});

// Handle pool errors - log but do not crash, let requests return 503
pool.on('error', (err, client) => {
  console.error('Unexpected error on idle PostgreSQL client:', err.message);
});

// Test connection on startup - log result but never exit
pool.query('SELECT NOW()', (err, res) => {
  if (err) {
    console.error('⚠️  Database not yet reachable on startup (will retry per-request):', err.message);
  } else {
    console.log('✅ Database connected successfully at:', res.rows[0].now);
  }
});

module.exports = {
  query: (text, params) => pool.query(text, params),
  pool
};