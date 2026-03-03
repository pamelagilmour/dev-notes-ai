'use client';

export default function Footer() {
  return (
    <footer className="bg-gray-900 text-white py-12 mt-auto">
      <div className="container mx-auto px-4 max-w-6xl">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-8 mb-8">
          {/* About */}
          <div>
            <h3 className="font-bold text-lg mb-4">Dev Notes AI</h3>
            <p className="text-gray-400 text-sm">
              A full-stack portfolio project demonstrating modern web development,
              AI integration, and production-grade security.
            </p>
          </div>
          
          {/* Technology Stack */}
          <div>
            <h4 className="font-semibold mb-4">Tech Stack</h4>
            <ul className="space-y-2 text-sm text-gray-400">
              <li>Next.js 14</li>
              <li>FastAPI + Python</li>
              <li>PostgreSQL</li>
              <li>Redis</li>
              <li>Claude AI (MCP)</li>
            </ul>
          </div>
          
          {/* Features */}
          <div>
            <h4 className="font-semibold mb-4">Features</h4>
            <ul className="space-y-2 text-sm text-gray-400">
              <li>JWT Authentication</li>
              <li>Rate Limiting</li>
              <li>Audit Logging</li>
              <li>Redis Caching</li>
              <li>Security Headers</li>
            </ul>
          </div>
          
          {/* Connect */}
          <div>
            <h4 className="font-semibold mb-4">Connect</h4>
            <ul className="space-y-2 text-sm">
              <li>
                <a 
                  href="https://github.com/pamelagilmour/dev-notes-ai" 
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-gray-400 hover:text-white transition flex items-center gap-2"
                >
                  <span>→</span> GitHub Repository
                </a>
              </li>
              <li>
                <a 
                  href="https://linkedin.com/in/pamelagilmour" 
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-gray-400 hover:text-white transition flex items-center gap-2"
                >
                  <span>→</span> LinkedIn
                </a>
              </li>
              <li>
                <a 
                  href="https://github.com/pamelagilmour" 
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-gray-400 hover:text-white transition flex items-center gap-2"
                >
                  <span>→</span> More Projects
                </a>
              </li>
            </ul>
          </div>
        </div>
        
        {/* Bottom Bar */}
        <div className="border-t border-gray-800 pt-8 flex flex-col md:flex-row justify-between items-center text-sm text-gray-400">
          <p>© 2024 Pamela Gilmour • Built as a portfolio project</p>
          <p className="mt-2 md:mt-0">Deployed on Vercel & Railway</p>
        </div>
      </div>
    </footer>
  );
}
