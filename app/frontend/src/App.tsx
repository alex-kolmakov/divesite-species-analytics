import { BrowserRouter, Routes, Route, Link, useLocation } from 'react-router-dom';
import SpeciesSearch from './pages/SpeciesSearch';
import DiveSiteExplorer from './pages/DiveSiteExplorer';
import './App.css';

function TopNav() {
  const onSites = useLocation().pathname.startsWith('/divesites');
  return (
    <nav className="topnav">
      <div className="topnav__brand">
        <span className="topnav__logo">🤿</span>
        <span className="topnav__wordmark">
          <span className="topnav__wordmark-accent">Marine</span> Species Explorer
        </span>
      </div>
      <div className="topnav__links">
        <Link to="/" className={onSites ? 'nav-link' : 'nav-link active'}>
          Species Search
        </Link>
        <Link to="/divesites" className={onSites ? 'nav-link active' : 'nav-link'}>
          Dive Sites
        </Link>
      </div>
    </nav>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <div className="app">
        <TopNav />
        <main className="main">
          <Routes>
            <Route path="/" element={<SpeciesSearch />} />
            <Route path="/species/:name" element={<SpeciesSearch />} />
            <Route path="/divesites" element={<DiveSiteExplorer />} />
            <Route path="/divesites/:siteId" element={<DiveSiteExplorer />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}
