import { useEffect, useRef, useState, useCallback } from "react";
import { MapPin, Search, AlertTriangle, Route, Clock, Check } from "lucide-react";
import type { ServiceCenter } from "../types";
import { BRAND } from "../utils/theme";

// Default location: Bengaluru city center
const DEFAULT_LAT = 12.9716;
const DEFAULT_LNG = 77.5946;

interface LocationPickerProps {
  address: string;
  latitude: number | null;
  longitude: number | null;
  selectedCenter: ServiceCenter | null;
  serviceCenters: ServiceCenter[];
  onChange: (data: { address: string; latitude: number; longitude: number }) => void;
}

// Haversine distance fallback (in km)
function calculateHaversineKm(lat1: number, lon1: number, lat2: number, lon2: number): number {
  const R = 6371;
  const dLat = ((lat2 - lat1) * Math.PI) / 180;
  const dLon = ((lon2 - lon1) * Math.PI) / 180;
  const a =
    Math.sin(dLat / 2) * Math.sin(dLat / 2) +
    Math.cos((lat1 * Math.PI) / 180) *
      Math.cos((lat2 * Math.PI) / 180) *
      Math.sin(dLon / 2) *
      Math.sin(dLon / 2);
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  return Math.round(R * c * 10) / 10;
}

export function GoogleLocationPicker({
  address,
  latitude,
  longitude,
  selectedCenter,
  serviceCenters,
  onChange,
}: LocationPickerProps) {
  const apiKey = (import.meta.env.VITE_GOOGLE_MAPS_API_KEY || "").trim();

  const [mapLoaded, setMapLoaded] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [searchInput, setSearchInput] = useState(address);
  const [currentLat, setCurrentLat] = useState<number>(latitude || DEFAULT_LAT);
  const [currentLng, setCurrentLng] = useState<number>(longitude || DEFAULT_LNG);
  const [distanceKm, setDistanceKm] = useState<number | null>(null);
  const [durationMins, setDurationMins] = useState<number | null>(null);

  const mapRef = useRef<HTMLDivElement>(null);
  const googleMapRef = useRef<any>(null);
  const markerRef = useRef<any>(null);
  const centerMarkersRef = useRef<any[]>([]);
  const searchInputRef = useRef<HTMLInputElement>(null);

  // Synchronize internal state with props
  useEffect(() => {
    if (latitude && longitude) {
      setCurrentLat(latitude);
      setCurrentLng(longitude);
    }
  }, [latitude, longitude]);

  useEffect(() => {
    if (address && address !== searchInput) {
      setSearchInput(address);
    }
  }, [address]);

  // Calculate distance and duration to selected center
  const updateDistanceMetrics = useCallback(
    (lat: number, lng: number, center: ServiceCenter | null) => {
      if (!center || typeof center.latitude !== "number" || typeof center.longitude !== "number") {
        setDistanceKm(null);
        setDurationMins(null);
        return;
      }

      const win = window as any;
      if (win.google?.maps?.geometry?.spherical) {
        const p1 = new win.google.maps.LatLng(lat, lng);
        const p2 = new win.google.maps.LatLng(center.latitude, center.longitude);
        const distMeters = win.google.maps.geometry.spherical.computeDistanceBetween(p1, p2);
        const distKm = Math.round((distMeters / 1000) * 10) / 10;
        const estimatedMins = Math.max(5, Math.ceil((distKm / 25) * 60)); // ~25 km/h urban speed
        setDistanceKm(distKm);
        setDurationMins(estimatedMins);
      } else {
        // Fallback Haversine calculation
        const distKm = calculateHaversineKm(lat, lng, center.latitude, center.longitude);
        const estimatedMins = Math.max(5, Math.ceil((distKm / 25) * 60));
        setDistanceKm(distKm);
        setDurationMins(estimatedMins);
      }
    },
    []
  );

  // Recalculate distance when location or selected center changes
  useEffect(() => {
    updateDistanceMetrics(currentLat, currentLng, selectedCenter);
  }, [currentLat, currentLng, selectedCenter, updateDistanceMetrics]);

  // Reverse geocode location to update address text
  const reverseGeocode = useCallback(
    (lat: number, lng: number) => {
      const win = window as any;
      if (win.google?.maps?.Geocoder) {
        const geocoder = new win.google.maps.Geocoder();
        geocoder.geocode({ location: { lat, lng } }, (results: any[], status: string) => {
          if (status === "OK" && results?.[0]) {
            const formatted = results[0].formatted_address;
            setSearchInput(formatted);
            onChange({ address: formatted, latitude: lat, longitude: lng });
          } else {
            onChange({ address: searchInput || "Custom Doorstep Pickup Location", latitude: lat, longitude: lng });
          }
        });
      } else {
        onChange({ address: searchInput || "Custom Doorstep Pickup Location", latitude: lat, longitude: lng });
      }
    },
    [onChange, searchInput]
  );

  // Load Google Maps Script
  useEffect(() => {
    if (!apiKey) return;

    (window as any).gm_authFailure = () => {
      setLoadError("Google Maps authentication failed. Please verify your VITE_GOOGLE_MAPS_API_KEY.");
    };

    if ((window as any).google?.maps) {
      setMapLoaded(true);
      return;
    }

    const scriptId = "google-maps-script";
    let script = document.getElementById(scriptId) as HTMLScriptElement;

    if (!script) {
      script = document.createElement("script");
      script.id = scriptId;
      script.src = `https://maps.googleapis.com/maps/api/js?key=${apiKey}&libraries=places,geometry`;
      script.async = true;
      script.defer = true;
      script.onload = () => setMapLoaded(true);
      script.onerror = () => setLoadError("Failed to load Google Maps script. Check network or API key.");
      document.head.appendChild(script);
    } else {
      script.addEventListener("load", () => setMapLoaded(true));
    }
  }, [apiKey]);

  // Initialize Google Map instance
  useEffect(() => {
    const win = window as any;
    if (!mapLoaded || !mapRef.current || !win.google?.maps) return;

    try {
      const mapOptions = {
        center: { lat: currentLat, lng: currentLng },
        zoom: 14,
        mapTypeControl: false,
        streetViewControl: false,
        fullscreenControl: false,
        zoomControl: true,
      };

      const map = new win.google.maps.Map(mapRef.current, mapOptions);
      googleMapRef.current = map;

      // Pickup Draggable Marker
      const pickupMarker = new win.google.maps.Marker({
        position: { lat: currentLat, lng: currentLng },
        map,
        draggable: true,
        title: "Drag to set pickup location",
        icon: {
          path: win.google.maps.SymbolPath.CIRCLE,
          scale: 10,
          fillColor: BRAND,
          fillOpacity: 1,
          strokeColor: "#ffffff",
          strokeWeight: 3,
        },
      });
      markerRef.current = pickupMarker;

      // Marker Drag End Listener
      pickupMarker.addListener("dragend", () => {
        const pos = pickupMarker.getPosition();
        if (pos) {
          const lat = pos.lat();
          const lng = pos.lng();
          setCurrentLat(lat);
          setCurrentLng(lng);
          reverseGeocode(lat, lng);
        }
      });

      // Map Click Listener
      map.addListener("click", (e: any) => {
        if (e.latLng) {
          const lat = e.latLng.lat();
          const lng = e.latLng.lng();
          pickupMarker.setPosition(e.latLng);
          setCurrentLat(lat);
          setCurrentLng(lng);
          reverseGeocode(lat, lng);
        }
      });

      // Places Autocomplete
      if (searchInputRef.current && win.google.maps.places) {
        const autocomplete = new win.google.maps.places.Autocomplete(searchInputRef.current, {
          types: ["geocode", "establishment"],
        });
        autocomplete.bindTo("bounds", map);

        autocomplete.addListener("place_changed", () => {
          const place = autocomplete.getPlace();
          if (place.geometry?.location) {
            const lat = place.geometry.location.lat();
            const lng = place.geometry.location.lng();
            map.setCenter(place.geometry.location);
            map.setZoom(15);
            pickupMarker.setPosition(place.geometry.location);
            setCurrentLat(lat);
            setCurrentLng(lng);
            const formatted = place.formatted_address || place.name || "";
            setSearchInput(formatted);
            onChange({ address: formatted, latitude: lat, longitude: lng });
          }
        });
      }
    } catch (err) {
      setLoadError("Could not initialize Google Map container.");
    }
  }, [mapLoaded, reverseGeocode, onChange]);

  // Render Service Center Markers on Map
  useEffect(() => {
    const win = window as any;
    if (!googleMapRef.current || !win.google?.maps || !serviceCenters.length) return;

    // Clear previous center markers
    centerMarkersRef.current.forEach((m) => m.setMap(null));
    centerMarkersRef.current = [];

    serviceCenters.forEach((center) => {
      if (typeof center.latitude === "number" && typeof center.longitude === "number") {
        const isSelected = selectedCenter?.id === center.id;
        const marker = new win.google.maps.Marker({
          position: { lat: center.latitude, lng: center.longitude },
          map: googleMapRef.current,
          title: center.name,
          icon: {
            path: win.google.maps.SymbolPath.BACKWARD_CLOSED_ARROW,
            scale: isSelected ? 8 : 6,
            fillColor: isSelected ? "#2563eb" : "#4b5563",
            fillOpacity: 0.9,
            strokeColor: "#ffffff",
            strokeWeight: 2,
          },
        });
        centerMarkersRef.current.push(marker);
      }
    });
  }, [serviceCenters, selectedCenter, mapLoaded]);

  // Fallback Preset Locations for Bengaluru
  const PRESETS = [
    { name: "Indiranagar, Bengaluru", lat: 12.9784, lng: 77.6408 },
    { name: "Koramangala 4th Block", lat: 12.9352, lng: 77.6245 },
    { name: "Yelahanka New Town", lat: 13.1007, lng: 77.5963 },
    { name: "Whitefield Main Road", lat: 12.9698, lng: 77.7499 },
    { name: "MG Road Metro Station", lat: 12.9756, lng: 77.6066 },
  ];

  const handleSelectPreset = (p: { name: string; lat: number; lng: number }) => {
    setCurrentLat(p.lat);
    setCurrentLng(p.lng);
    setSearchInput(p.name);
    onChange({ address: p.name, latitude: p.lat, longitude: p.lng });

    if (googleMapRef.current && markerRef.current) {
      const pos = { lat: p.lat, lng: p.lng };
      googleMapRef.current.setCenter(pos);
      markerRef.current.setPosition(pos);
    }
  };

  // If no API Key or Load Error: Render Non-Crashing Graceful Fallback
  if (!apiKey || loadError) {
    return (
      <div className="space-y-3 rounded-3xl border border-amber-200/80 bg-amber-50/60 p-5 dark:border-amber-900/40 dark:bg-amber-950/20">
        <div className="flex items-start gap-3">
          <AlertTriangle size={22} className="text-amber-600 dark:text-amber-400 shrink-0 mt-0.5" />
          <div>
            <h4 className="text-sm font-bold text-amber-900 dark:text-amber-300">
              Google Maps Configuration Required
            </h4>
            <p className="text-xs text-amber-700 dark:text-amber-400 mt-0.5">
              {!apiKey
                ? "Set VITE_GOOGLE_MAPS_API_KEY in client/.env to enable interactive maps."
                : loadError}
            </p>
          </div>
        </div>

        {/* Address Search / Text Input Fallback */}
        <label className="block text-xs font-bold text-zinc-700 dark:text-zinc-300">
          Pickup Address Text
          <div className="relative mt-1">
            <input
              type="text"
              className="w-full rounded-2xl border border-zinc-200 bg-white px-4 py-2.5 pl-10 text-sm dark:border-zinc-700 dark:bg-zinc-900"
              placeholder="Enter your doorstep pickup address"
              value={searchInput}
              onChange={(e) => {
                setSearchInput(e.target.value);
                onChange({ address: e.target.value, latitude: currentLat, longitude: currentLng });
              }}
            />
            <MapPin size={16} className="absolute left-3.5 top-3 text-brand-fg" />
          </div>
        </label>

        {/* Quick Location Presets */}
        <div>
          <span className="text-[11px] font-bold text-zinc-500 uppercase tracking-wider block mb-1.5">
            Quick Location Presets (Bengaluru)
          </span>
          <div className="flex flex-wrap gap-1.5">
            {PRESETS.map((p) => (
              <button
                key={p.name}
                type="button"
                onClick={() => handleSelectPreset(p)}
                className="rounded-xl border border-zinc-200 bg-white px-2.5 py-1 text-xs font-semibold text-zinc-700 hover:border-brand dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-300"
              >
                {p.name.split(",")[0]}
              </button>
            ))}
          </div>
        </div>

        {/* Distance Badge using Haversine Fallback */}
        {selectedCenter && (
          <div className="flex items-center justify-between rounded-2xl bg-white p-3 dark:bg-zinc-900 border border-zinc-200/80 dark:border-zinc-800 text-xs">
            <span className="font-semibold text-zinc-600 dark:text-zinc-400">
              Distance to {selectedCenter.name}:
            </span>
            <div className="flex items-center gap-3 font-bold">
              <span className="flex items-center gap-1 text-blue-600 dark:text-blue-400">
                <Route size={14} /> {distanceKm ?? "—"} km
              </span>
              <span className="flex items-center gap-1 text-emerald-600 dark:text-emerald-400">
                <Clock size={14} /> ~{durationMins ?? "—"} mins
              </span>
            </div>
          </div>
        )}
      </div>
    );
  }

  // Render Full Interactive Google Map Component
  return (
    <div className="space-y-3">
      {/* Places Search Bar */}
      <div className="relative">
        <input
          ref={searchInputRef}
          type="text"
          className="w-full rounded-2xl border border-zinc-200 bg-white px-4 py-2.5 pl-10 pr-10 text-sm shadow-sm dark:border-zinc-700 dark:bg-zinc-900"
          placeholder="Search for pickup address, locality or landmark..."
          value={searchInput}
          onChange={(e) => setSearchInput(e.target.value)}
        />
        <Search size={17} className="absolute left-3.5 top-3 text-zinc-400" />
        {searchInput && (
          <button
            type="button"
            onClick={() => setSearchInput("")}
            className="absolute right-3.5 top-3 text-xs font-bold text-zinc-400 hover:text-zinc-600"
          >
            Clear
          </button>
        )}
      </div>

      {/* Map Canvas Container */}
      <div className="relative overflow-hidden rounded-3xl border border-zinc-200 shadow-inner dark:border-zinc-700">
        <div ref={mapRef} className="h-64 w-full bg-zinc-100 dark:bg-zinc-800" />

        {/* Map Overlay Instruction Badge */}
        <div className="absolute top-3 left-3 flex items-center gap-1.5 rounded-full bg-zinc-900/80 px-3 py-1 text-xs font-semibold text-white backdrop-blur-sm">
          <MapPin size={13} className="text-brand-fg" />
          <span>Click map or drag red marker to pinpoint pickup</span>
        </div>

        {/* Current Coordinates Badge */}
        <div className="absolute bottom-3 left-3 rounded-xl bg-white/90 px-2.5 py-1 text-[11px] font-mono font-medium text-zinc-700 shadow-sm backdrop-blur-sm dark:bg-zinc-900/90 dark:text-zinc-300">
          {currentLat.toFixed(4)}, {currentLng.toFixed(4)}
        </div>
      </div>

      {/* Selected Center & Distance Info Bar */}
      {selectedCenter && (
        <div className="flex flex-wrap items-center justify-between gap-2 rounded-2xl bg-zinc-100/90 p-3 text-xs dark:bg-zinc-800/90">
          <div className="flex items-center gap-2">
            <span className="rounded-full bg-blue-500/15 p-1 text-blue-600 dark:text-blue-400">
              <Check size={14} />
            </span>
            <span>
              Hub: <strong>{selectedCenter.name}</strong>
            </span>
          </div>

          <div className="flex items-center gap-3 font-bold">
            <span className="flex items-center gap-1 text-blue-600 dark:text-blue-400">
              <Route size={14} /> {distanceKm !== null ? `${distanceKm} km` : "Calculating..."}
            </span>
            <span className="flex items-center gap-1 text-emerald-600 dark:text-emerald-400">
              <Clock size={14} /> {durationMins !== null ? `~${durationMins} mins` : ""}
            </span>
          </div>
        </div>
      )}
    </div>
  );
}
