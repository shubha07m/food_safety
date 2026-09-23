// Synthetic browser-transport fixture only; no recorded provider response.
window.__foodpathMapInstances = 0;
window.google = { maps: {
  SymbolPath: { CIRCLE: 'circle' },
  LatLngBounds: class { constructor() { this.points = []; } extend(p) { this.points.push(p); } },
  InfoWindow: class {
    constructor() { window.__foodpathInfo = this; }
    setContent(c) { this.content = c; } setPosition() {} open() {} close() {}
  },
  Map: class {
    constructor(container) {
      window.__foodpathMapInstances++; window.__foodpathTestMap = this;
      container.textContent = 'SYNTHETIC MAP TRANSPORT TEST — NOT GOOGLE MAP IMAGERY';
      const data = this.data = { features: [], listeners: {},
        forEach(fn) { [...this.features].forEach(fn); },
        remove(f) { this.features = this.features.filter(x => x !== f); },
        addGeoJson(collection) { this.features = collection.features.map(f => ({...f,getId:()=>f.id,getProperty:k=>f.properties[k]})); },
        setStyle(style) { this.style = style; }, addListener(name,fn) { this.listeners[name] = fn; },
      };
      data.features = [];
    }
    fitBounds(b) { this.bounds = b.points; }
    setCenter(c) { this.center = c; }
    setZoom(z) { this.zoom = z; }
  },
} };
window.foodpathMapLoaded();
