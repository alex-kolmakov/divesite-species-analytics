import { BrowserRouter, Routes, Route, NavLink } from 'react-router-dom';
import SpeciesSearch from './pages/SpeciesSearch';
import DiveSiteExplorer from './pages/DiveSiteExplorer';
import './App.css';

export default function App() {
  return (
    <BrowserRouter>
      <div className="app">
        <nav className="topnav">
          <div className="topnav__brand">
            <span className="topnav__logo">🤿</span>
            <span className="topnav__wordmark">
              <span className="topnav__wordmark-accent">Marine</span> Species Explorer
            </span>
          </div>
          <div className="topnav__links">
            <NavLink to="/" end className={({ isActive }) => isActive ? 'nav-link active' : 'nav-link'}>
              Species Search
            </NavLink>
            <NavLink to="/divesites" className={({ isActive }) => isActive ? 'nav-link active' : 'nav-link'}>
              Dive Sites
            </NavLink>
          </div>
        </nav>
        <main className="main">
          <Routes>
            <Route path="/" element={<SpeciesSearch />} />
            <Route path="/divesites" element={<DiveSiteExplorer />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}
