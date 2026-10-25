import { useEffect, useRef, useState, useCallback } from "react";
import { MapPin, Search, Route, Clock, Check } from "lucide-react";
import type { ServiceCenter } from "../types";
import { BRAND } from "../utils/theme";
import { drivingMinutes, haversineKm } from "../utils/geo";
import { OsmLocationPicker } from "./OsmLocationPicker";

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
        setDistanceKm(distKm);
        setDurationMins(drivingMinutes(distKm));
      } else {
        // Fallback Haversine calculation
        const distKm = haversineKm(lat, lng, center.latitude, center.longitude);
        setDistanceKm(distKm);
        setDurationMins(drivingMinutes(distKm));
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

  // Without a Google key (or if Google fails to load), use the free OpenStreetMap picker instead
  if (!apiKey || loadError) {
    return (
      <OsmLocationPicker
        address={address}
        latitude={latitude}
        longitude={longitude}
        selectedCenter={selectedCenter}
        serviceCenters={serviceCenters}
        onChange={onChange}
      />
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
          <span>Click the map or drag the marker to set your pickup point</span>
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
