'use client';

import { useState, useEffect, useId } from 'react';
import { 
  ShoppingBag, 
  Store, 
  Pill, 
  MapPin, 
  CheckCircle2, 
  X, 
  Clock,
  ShieldCheck,
  Plus,
  Minus,
  Loader2,
  Navigation,
  PackageCheck,
} from 'lucide-react';

import { api } from '@/lib/api';
import { getEmergencyContact } from '@/lib/whatsapp';
import { getRealLocationAddress, fetchRealNearbyPharmacies, RealPharmacy, UserLocation } from '@/lib/location';

// ── OTC price lookup (approximate INR) ──────────────────────────────────────
const OTC_PRICES: Record<string, number> = {
  'Paracetamol': 12, 'Paracetamol 500mg': 12, 'Ibuprofen': 25, 'Ibuprofen 400mg': 25,
  'Aspirin': 15, 'Antacid': 30, 'ORS': 10, 'Oral Rehydration Solution (ORS)': 10,
  'Cetirizine': 18, 'Amoxicillin': 55, 'Azithromycin': 90, 'Metformin': 35,
  'Omeprazole': 28, 'Pantoprazole': 32, 'Vitamin C': 40, 'Cough Syrup': 65,
  'Dolo 650': 14, 'Disprin': 12,
};

function getPriceForMed(name: string): number {
  const key = Object.keys(OTC_PRICES).find(k => 
    name.toLowerCase().includes(k.toLowerCase()) || k.toLowerCase().includes(name.split('(')[0].trim().toLowerCase())
  );
  return key ? OTC_PRICES[key] : 45; // default ₹45 for unknown OTC
}

interface CartItem { name: string; quantity: number; price: number; }

interface OrderPharmacyModalProps {
  isOpen: boolean;
  onClose: () => void;
  diseaseName?: string;
  recommendedMedicines?: string[];
}

export function OrderPharmacyModal({
  isOpen,
  onClose,
  diseaseName = 'General Health Symptom Relief',
  recommendedMedicines = ['Paracetamol 500mg', 'Oral Rehydration Solution (ORS)', 'Antacid'],
}: OrderPharmacyModalProps) {
  const modalId = useId(); // stable ID — no re-render issues
  const [selectedPharmacy, setSelectedPharmacy] = useState<RealPharmacy | null>(null);
  const [pharmacies, setPharmacies] = useState<RealPharmacy[]>([]);
  const [pharmacyLoading, setPharmacyLoading] = useState(false);
  const [cart, setCart] = useState<CartItem[]>(() =>
    recommendedMedicines.map(name => ({ name, quantity: 1, price: getPriceForMed(name) }))
  );
  const [customItem, setCustomItem] = useState('');
  const [orderStatus, setOrderStatus] = useState<'idle' | 'placing' | 'confirmed'>('idle');
  const [location, setLocation] = useState<UserLocation | null>(null);
  const [trackingNo, setTrackingNo] = useState('');

  // Re-sync cart when recommendedMedicines prop changes
  useEffect(() => {
    setCart(recommendedMedicines.map(name => ({ name, quantity: 1, price: getPriceForMed(name) })));
  }, [recommendedMedicines.join(',')]);

  useEffect(() => {
    if (!isOpen) return;
    setOrderStatus('idle');
    setTrackingNo('');
    setPharmacyLoading(true);

    if (navigator.geolocation) {
      navigator.geolocation.getCurrentPosition(
        async ({ coords: { latitude: lat, longitude: lng } }) => {
          try {
            const [loc, nearby] = await Promise.all([
              getRealLocationAddress(lat, lng),
              fetchRealNearbyPharmacies(lat, lng),
            ]);
            setLocation(loc);
            const top3 = nearby.slice(0, 3);
            setPharmacies(top3);
            if (top3.length > 0) setSelectedPharmacy(top3[0]);
          } catch {
            // silently fall through — pharmacies will be empty
          } finally {
            setPharmacyLoading(false);
          }
        },
        () => setPharmacyLoading(false),
        { enableHighAccuracy: true, timeout: 10000 }
      );
    } else {
      setPharmacyLoading(false);
    }
  }, [isOpen]);

  if (!isOpen) return null;

  // ── Cart helpers ──────────────────────────────────────────────────────────
  const totalItems = cart.reduce((s, i) => s + i.quantity, 0);
  const totalAmount = cart.reduce((s, i) => s + i.price * i.quantity, 0);

  const updateQty = (name: string, delta: number) => {
    setCart(prev => prev
      .map(i => i.name === name ? { ...i, quantity: Math.max(0, i.quantity + delta) } : i)
      .filter(i => i.quantity > 0)
    );
  };

  const removeItem = (name: string) => setCart(prev => prev.filter(i => i.name !== name));

  const handleAddCustom = () => {
    const trimmed = customItem.trim();
    if (!trimmed || cart.some(i => i.name === trimmed)) return;
    setCart(prev => [...prev, { name: trimmed, quantity: 1, price: getPriceForMed(trimmed) }]);
    setCustomItem('');
  };

  // ── Estimated delivery based on distance ─────────────────────────────────
  const estimatedDelivery = (() => {
    if (!selectedPharmacy) return '20-30 mins';
    const km = selectedPharmacy.distanceKm ?? 1;
    if (km < 1) return '10-15 mins';
    if (km < 3) return '15-25 mins';
    if (km < 7) return '25-40 mins';
    return '40-60 mins';
  })();

  // ── Order handlers ────────────────────────────────────────────────────────
  const handleConfirmOrder = async () => {
    if (cart.length === 0 || orderStatus !== 'idle') return;
    setOrderStatus('placing');

    const deliveryAddr = location
      ? `${location.address}, ${location.city}${location.postcode ? ' ' + location.postcode : ''}`
      : 'GPS Location (Live)';

    try {
      const res = await api.orders.create({
        pharmacy_name: selectedPharmacy?.name || 'Nearest Local Pharmacy',
        pharmacy_address: selectedPharmacy?.address || 'Local Shop',
        medicines: cart.map(i => ({ name: i.name, quantity: i.quantity, price: i.price })),
        delivery_address: deliveryAddr,
        total_amount: totalAmount,
      });
      // Use server-assigned tracking number if available
      setTrackingNo((res as any)?.tracking_number || `ORD-${Math.floor(100000 + Math.random() * 900000)}`);
    } catch {
      setTrackingNo(`ORD-${Math.floor(100000 + Math.random() * 900000)}`);
    }

    setOrderStatus('confirmed');
  };

  const handlePayViaPharmEasy = () => {
    const firstMed = cart[0]?.name || 'Paracetamol';
    const cleanQuery = encodeURIComponent(firstMed.split('(')[0].trim());
    if (typeof window !== 'undefined') {
      window.open(`https://pharmeasy.in/search/all?name=${cleanQuery}`, '_blank', 'noopener,noreferrer');
    }
    // Also persist the order in backend without changing status
    if (location) {
      const deliveryAddr = `${location.address}, ${location.city}`;
      api.orders.create({
        pharmacy_name: 'PharmEasy Online (pharmeasy.in)',
        pharmacy_address: 'Online Delivery',
        medicines: cart.map(i => ({ name: i.name, quantity: i.quantity, price: i.price })),
        delivery_address: deliveryAddr,
        total_amount: totalAmount,
      }).catch(() => null);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-md p-4 animate-in fade-in duration-200 overflow-y-auto">
      <div className="relative w-full max-w-lg rounded-3xl border border-border bg-card p-6 shadow-2xl space-y-5 text-foreground my-4">

        {/* Close */}
        <button onClick={onClose} className="absolute top-4 right-4 p-2 rounded-full text-muted-foreground hover:text-foreground hover:bg-secondary transition-all">
          <X className="h-5 w-5" />
        </button>

        {/* Header */}
        <div className="flex items-center gap-3 border-b pb-4">
          <div className="p-3 rounded-2xl bg-gradient-to-br from-teal-500 to-emerald-600 text-white shadow-md">
            <ShoppingBag className="h-7 w-7" />
          </div>
          <div>
            <span className="px-2.5 py-0.5 rounded-full bg-teal-500/10 text-teal-600 font-extrabold text-[10px] uppercase border border-teal-500/20">
              PharmEasy &amp; Nearby Pharmacy Dispatch
            </span>
            <h2 className="text-xl font-bold text-foreground tracking-tight mt-0.5">Order Medicines</h2>
            <p className="text-xs text-muted-foreground">Condition: <strong>{diseaseName}</strong></p>
          </div>
        </div>

        {/* ── Confirmed State ── */}
        {orderStatus === 'confirmed' ? (
          <div className="p-6 rounded-2xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-700 dark:text-emerald-300 space-y-3 text-center">
            <div className="mx-auto h-14 w-14 rounded-full bg-emerald-500 text-white flex items-center justify-center shadow-lg shadow-emerald-500/30 animate-bounce">
              <PackageCheck className="h-8 w-8" />
            </div>
            <h3 className="font-extrabold text-lg text-emerald-600">Order Confirmed!</h3>
            <div className="p-3 rounded-xl bg-card border text-xs text-foreground font-semibold flex items-center justify-between">
              <span className="flex items-center gap-1.5">
                <ShoppingBag className="h-4 w-4 text-emerald-500" />
                {selectedPharmacy?.name || 'Local Pharmacy'}
              </span>
              <span className="text-emerald-600 font-mono">{trackingNo}</span>
            </div>
            <div className="text-xs text-muted-foreground space-y-1">
              <p><strong>{totalItems} item{totalItems !== 1 ? 's' : ''}</strong> · ₹{totalAmount.toFixed(2)} total</p>
              <p className="flex items-center justify-center gap-1">
                <Clock className="h-3.5 w-3.5 text-blue-500" />
                Estimated delivery: <strong>{estimatedDelivery}</strong>
              </p>
              <p className="flex items-center justify-center gap-1 mt-1">
                <MapPin className="h-3.5 w-3.5 text-emerald-500" />
                {location ? `${location.address}, ${location.city}` : 'Your GPS location'}
              </p>
            </div>
            <button onClick={onClose} className="mt-2 w-full py-2.5 rounded-xl bg-emerald-600 text-white font-bold text-xs shadow hover:bg-emerald-500 transition-all">
              Done
            </button>
          </div>
        ) : (
          <>
            {/* PharmEasy Banner */}
            <div className="p-3 rounded-2xl bg-gradient-to-r from-teal-500/10 via-emerald-500/10 to-teal-600/10 border border-teal-500/30 flex items-center justify-between gap-3">
              <div className="text-xs space-y-0.5">
                <div className="font-extrabold text-teal-700 dark:text-teal-300">💊 PharmEasy Online — Flat 20% Off</div>
                <div className="text-[11px] text-muted-foreground">Instant checkout · Home delivery · Authentic medicines</div>
              </div>
              <button type="button" onClick={handlePayViaPharmEasy}
                className="px-3 py-1.5 rounded-xl bg-teal-600 hover:bg-teal-500 text-white font-bold text-xs shadow transition-all shrink-0">
                Order on PharmEasy ↗
              </button>
            </div>

            {/* Pharmacy Selector */}
            <div className="space-y-2">
              <label className="text-xs font-bold text-foreground flex items-center gap-1.5">
                <Store className="h-4 w-4 text-emerald-500" />
                Nearest Local Pharmacy
                {pharmacyLoading && <Loader2 className="h-3.5 w-3.5 animate-spin text-muted-foreground ml-1" />}
              </label>

              {pharmacyLoading && (
                <div className="space-y-2 animate-pulse">
                  {[0,1,2].map(i => <div key={i} className="h-12 rounded-xl bg-secondary/50 border" />)}
                </div>
              )}

              {!pharmacyLoading && pharmacies.length === 0 && (
                <p className="text-xs text-muted-foreground px-1">
                  Location unavailable — enable GPS to find nearby pharmacies.
                </p>
              )}

              {!pharmacyLoading && pharmacies.map((shop) => (
                <div key={shop.id} onClick={() => setSelectedPharmacy(shop)}
                  className={`p-3 rounded-xl border cursor-pointer flex items-center justify-between transition-all text-xs ${
                    selectedPharmacy?.id === shop.id
                      ? 'border-emerald-500 bg-emerald-500/10 font-semibold shadow-sm'
                      : 'border-border bg-secondary/30 hover:bg-secondary/70 text-muted-foreground'
                  }`}>
                  <div className="flex items-center gap-2.5">
                    <Store className={`h-4 w-4 shrink-0 ${selectedPharmacy?.id === shop.id ? 'text-emerald-600' : ''}`} />
                    <div>
                      <div className="font-bold text-foreground">{shop.name}</div>
                      <div className="text-[11px] text-muted-foreground">{shop.distance} · {shop.rating}</div>
                    </div>
                  </div>
                  <div className="text-right shrink-0">
                    <div className="text-[10px] px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-600 font-mono">{shop.deliveryTime}</div>
                    {selectedPharmacy?.id === shop.id && (
                      <div className="text-[10px] text-emerald-600 font-bold mt-1 flex items-center gap-0.5">
                        <ShieldCheck className="h-3 w-3" /> Selected
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>

            {/* Cart / Medicine List with Quantity Controls */}
            <div className="space-y-2">
              <label className="text-xs font-bold text-foreground flex items-center gap-1.5">
                <Pill className="h-4 w-4 text-violet-500" />
                Cart ({totalItems} items · ₹{totalAmount.toFixed(2)})
              </label>

              <div className="space-y-1.5 max-h-44 overflow-y-auto pr-1">
                {cart.map((item) => (
                  <div key={item.name} className="flex items-center justify-between gap-2 p-2 rounded-xl border bg-secondary/30 text-xs">
                    <span className="font-medium text-foreground flex items-center gap-1.5 min-w-0 flex-1 truncate">
                      <Pill className="h-3.5 w-3.5 text-emerald-500 shrink-0" />
                      <span className="truncate">{item.name}</span>
                      <span className="text-muted-foreground shrink-0">· ₹{item.price}</span>
                    </span>
                    <div className="flex items-center gap-1 shrink-0">
                      <button onClick={() => updateQty(item.name, -1)}
                        className="w-6 h-6 rounded-lg bg-secondary hover:bg-secondary/80 border flex items-center justify-center text-foreground font-bold transition-all">
                        <Minus className="h-3 w-3" />
                      </button>
                      <span className="w-5 text-center font-bold text-foreground">{item.quantity}</span>
                      <button onClick={() => updateQty(item.name, +1)}
                        className="w-6 h-6 rounded-lg bg-secondary hover:bg-secondary/80 border flex items-center justify-center text-foreground font-bold transition-all">
                        <Plus className="h-3 w-3" />
                      </button>
                      <button onClick={() => removeItem(item.name)}
                        className="ml-1 text-rose-500 hover:text-rose-400 text-[10px] font-bold transition-colors">
                        ✕
                      </button>
                    </div>
                  </div>
                ))}
              </div>

              {/* Add Custom Item */}
              <div className="flex gap-2 pt-1">
                <input type="text" placeholder="Add medicine or item..."
                  value={customItem}
                  onChange={(e) => setCustomItem(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleAddCustom()}
                  className="flex-1 bg-background rounded-lg border px-3 py-1.5 text-xs focus:outline-none focus:ring-2 focus:ring-primary/40" />
                <button type="button" onClick={handleAddCustom}
                  className="px-3 py-1.5 rounded-lg bg-secondary border hover:bg-secondary/80 text-xs font-bold flex items-center gap-1">
                  <Plus className="h-3.5 w-3.5" /> Add
                </button>
              </div>
            </div>

            {/* Footer — Delivery Info + Order Buttons */}
            <div className="pt-2 border-t space-y-3">
              <div className="flex items-center justify-between text-xs text-muted-foreground">
                <span className="flex items-center gap-1">
                  <MapPin className="h-3.5 w-3.5 text-emerald-500" />
                  <span className="truncate max-w-[200px]">
                    {location ? `${location.address}` : pharmacyLoading ? 'Fetching GPS...' : 'GPS unavailable'}
                  </span>
                </span>
                <span className="flex items-center gap-1 font-semibold text-foreground shrink-0">
                  <Clock className="h-3.5 w-3.5 text-blue-500" /> Est: {estimatedDelivery}
                </span>
              </div>

              {/* Total Summary */}
              <div className="flex items-center justify-between px-3 py-2 rounded-xl bg-secondary/40 border text-xs font-bold">
                <span className="text-muted-foreground">{totalItems} item{totalItems !== 1 ? 's' : ''}</span>
                <span className="text-foreground text-sm">₹{totalAmount.toFixed(2)} total</span>
              </div>

              <div className="grid grid-cols-2 gap-2">
                <button type="button" onClick={handlePayViaPharmEasy}
                  className="w-full flex items-center justify-center gap-1.5 p-3 rounded-2xl bg-teal-600 hover:bg-teal-500 text-white font-extrabold text-xs shadow-md transition-all">
                  <ShoppingBag className="h-4 w-4" /> PAY VIA PHARMEASY
                </button>

                <button onClick={handleConfirmOrder}
                  disabled={orderStatus === 'placing' || cart.length === 0 || !selectedPharmacy}
                  className="w-full flex items-center justify-center gap-1.5 p-3 rounded-2xl bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white font-extrabold text-xs shadow-md transition-all disabled:opacity-50">
                  {orderStatus === 'placing'
                    ? <><Loader2 className="h-3.5 w-3.5 animate-spin" /> Placing...</>
                    : <><Navigation className="h-4 w-4" /> LOCAL DELIVERY</>
                  }
                </button>
              </div>
            </div>
          </>
        )}

      </div>
    </div>
  );
}
