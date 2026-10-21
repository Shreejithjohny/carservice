from django.core.management.base import BaseCommand
from api.models import CarBrand, CarModel, CarVariant

CATALOG = {
    "Maruti Suzuki": {
        "Baleno": [
            {"name": "Sigma 1.2", "fuel_type": "Petrol", "transmission": "Manual", "engine": "1.2L DualJet"},
            {"name": "Delta 1.2", "fuel_type": "Petrol", "transmission": "Manual", "engine": "1.2L DualJet"},
            {"name": "Zeta 1.2 AMT", "fuel_type": "Petrol", "transmission": "AMT", "engine": "1.2L DualJet"},
            {"name": "Alpha 1.2 AMT", "fuel_type": "Petrol", "transmission": "AMT", "engine": "1.2L DualJet"},
            {"name": "Delta CNG", "fuel_type": "CNG", "transmission": "Manual", "engine": "1.2L K12N"},
        ],
        "Swift": [
            {"name": "LXi", "fuel_type": "Petrol", "transmission": "Manual", "engine": "1.2L Z12E"},
            {"name": "VXi", "fuel_type": "Petrol", "transmission": "Manual", "engine": "1.2L Z12E"},
            {"name": "ZXi AMT", "fuel_type": "Petrol", "transmission": "AMT", "engine": "1.2L Z12E"},
            {"name": "ZXi+ Dual Tone", "fuel_type": "Petrol", "transmission": "AMT", "engine": "1.2L Z12E"},
        ],
        "Brezza": [
            {"name": "LXi", "fuel_type": "Petrol", "transmission": "Manual", "engine": "1.5L K15C"},
            {"name": "VXi", "fuel_type": "Petrol", "transmission": "Manual", "engine": "1.5L K15C"},
            {"name": "ZXi AT", "fuel_type": "Petrol", "transmission": "Automatic", "engine": "1.5L K15C"},
            {"name": "ZXi+ Dual Tone AT", "fuel_type": "Petrol", "transmission": "Automatic", "engine": "1.5L K15C"},
        ],
        "Ertiga": [
            {"name": "LXi", "fuel_type": "Petrol", "transmission": "Manual", "engine": "1.5L K15C"},
            {"name": "VXi CNG", "fuel_type": "CNG", "transmission": "Manual", "engine": "1.5L K15C"},
            {"name": "ZXi AT", "fuel_type": "Petrol", "transmission": "Automatic", "engine": "1.5L K15C"},
        ],
        "Fronx": [
            {"name": "Delta 1.2", "fuel_type": "Petrol", "transmission": "Manual", "engine": "1.2L K12N"},
            {"name": "Zeta 1.0 Turbo", "fuel_type": "Petrol", "transmission": "Automatic", "engine": "1.0L Boosterjet"},
        ],
        "Grand Vitara": [
            {"name": "Delta 1.5 Smart Hybrid", "fuel_type": "Petrol", "transmission": "Manual", "engine": "1.5L K15C"},
            {"name": "Zeta+ Strong Hybrid", "fuel_type": "Hybrid", "transmission": "CVT", "engine": "1.5L TNGA"},
        ],
    },
    "Hyundai": {
        "Creta": [
            {"name": "E 1.5 Petrol", "fuel_type": "Petrol", "transmission": "Manual", "engine": "1.5L MPi"},
            {"name": "EX 1.5 Diesel", "fuel_type": "Diesel", "transmission": "Manual", "engine": "1.5L CRDi"},
            {"name": "SX (O) 1.5 IVT", "fuel_type": "Petrol", "transmission": "CVT", "engine": "1.5L MPi"},
            {"name": "SX (O) 1.5 Turbo DCT", "fuel_type": "Petrol", "transmission": "DCT", "engine": "1.5L Turbo GDi"},
        ],
        "i20": [
            {"name": "Magna 1.2", "fuel_type": "Petrol", "transmission": "Manual", "engine": "1.2L Kappa"},
            {"name": "Asta (O) IVT", "fuel_type": "Petrol", "transmission": "CVT", "engine": "1.2L Kappa"},
        ],
        "Venue": [
            {"name": "S 1.2 Petrol", "fuel_type": "Petrol", "transmission": "Manual", "engine": "1.2L Kappa"},
            {"name": "SX 1.5 Diesel", "fuel_type": "Diesel", "transmission": "Manual", "engine": "1.5L CRDi"},
            {"name": "SX (O) 1.0 Turbo DCT", "fuel_type": "Petrol", "transmission": "DCT", "engine": "1.0L Turbo GDi"},
        ],
        "Verna": [
            {"name": "EX 1.5", "fuel_type": "Petrol", "transmission": "Manual", "engine": "1.5L MPi"},
            {"name": "SX (O) 1.5 Turbo DCT", "fuel_type": "Petrol", "transmission": "DCT", "engine": "1.5L Turbo GDi"},
        ],
    },
    "Tata": {
        "Nexon": [
            {"name": "Smart 1.2 Revotron", "fuel_type": "Petrol", "transmission": "Manual", "engine": "1.2L Turbo"},
            {"name": "Creative 1.5 Revotorq", "fuel_type": "Diesel", "transmission": "Manual", "engine": "1.5L Diesel"},
            {"name": "Fearless+ S DCA", "fuel_type": "Petrol", "transmission": "DCT", "engine": "1.2L Turbo"},
            {"name": "Nexon EV Empowered+", "fuel_type": "Electric", "transmission": "Automatic", "engine": "Permanent Magnet Synchronous"},
        ],
        "Punch": [
            {"name": "Pure 1.2", "fuel_type": "Petrol", "transmission": "Manual", "engine": "1.2L Revotron"},
            {"name": "Accomplished Dazzle AMT", "fuel_type": "Petrol", "transmission": "AMT", "engine": "1.2L Revotron"},
            {"name": "Creative iCNG", "fuel_type": "CNG", "transmission": "Manual", "engine": "1.2L Revotron"},
        ],
        "Harrier": [
            {"name": "Pure+ 2.0", "fuel_type": "Diesel", "transmission": "Manual", "engine": "2.0L Kryotec"},
            {"name": "Fearless+ Dark AT", "fuel_type": "Diesel", "transmission": "Automatic", "engine": "2.0L Kryotec"},
        ],
        "Safari": [
            {"name": "Pure+ 2.0", "fuel_type": "Diesel", "transmission": "Manual", "engine": "2.0L Kryotec"},
            {"name": "Accomplished+ Dark AT", "fuel_type": "Diesel", "transmission": "Automatic", "engine": "2.0L Kryotec"},
        ],
        "Tiago": [
            {"name": "XE 1.2", "fuel_type": "Petrol", "transmission": "Manual", "engine": "1.2L Revotron"},
            {"name": "XZ+ iCNG AMT", "fuel_type": "CNG", "transmission": "AMT", "engine": "1.2L Revotron"},
        ],
    },
    "Mahindra": {
        "Thar": [
            {"name": "AX (O) Hard Top Diesel RWD", "fuel_type": "Diesel", "transmission": "Manual", "engine": "1.5L D117"},
            {"name": "LX Hard Top Petrol AT 4WD", "fuel_type": "Petrol", "transmission": "Automatic", "engine": "2.0L mStallion"},
            {"name": "LX Hard Top Diesel AT 4WD", "fuel_type": "Diesel", "transmission": "Automatic", "engine": "2.2L mHawk"},
        ],
        "XUV700": [
            {"name": "AX3 Petrol MT 5-Str", "fuel_type": "Petrol", "transmission": "Manual", "engine": "2.0L mStallion"},
            {"name": "AX7 Diesel AT AWD 7-Str", "fuel_type": "Diesel", "transmission": "Automatic", "engine": "2.2L mHawk"},
            {"name": "AX7L Diesel AT 7-Str", "fuel_type": "Diesel", "transmission": "Automatic", "engine": "2.2L mHawk"},
        ],
        "Scorpio N": [
            {"name": "Z4 Diesel MT 2WD", "fuel_type": "Diesel", "transmission": "Manual", "engine": "2.2L mHawk"},
            {"name": "Z8L Diesel AT 4WD", "fuel_type": "Diesel", "transmission": "Automatic", "engine": "2.2L mHawk"},
        ],
        "Bolero Neo": [
            {"name": "N4 1.5", "fuel_type": "Diesel", "transmission": "Manual", "engine": "1.5L mHawk75"},
            {"name": "N10 Option", "fuel_type": "Diesel", "transmission": "Manual", "engine": "1.5L mHawk75"},
        ],
    },
    "Toyota": {
        "Innova Crysta": [
            {"name": "GX 7-STR 2.4", "fuel_type": "Diesel", "transmission": "Manual", "engine": "2.4L GD"},
            {"name": "VX 7-STR 2.4", "fuel_type": "Diesel", "transmission": "Manual", "engine": "2.4L GD"},
        ],
        "Innova Hycross": [
            {"name": "GX 8-STR 2.0 Petrol", "fuel_type": "Petrol", "transmission": "CVT", "engine": "2.0L M20A"},
            {"name": "ZX (O) Hybrid 7-STR", "fuel_type": "Hybrid", "transmission": "CVT", "engine": "2.0L Hybrid"},
        ],
        "Fortuner": [
            {"name": "4x2 2.7 Petrol MT", "fuel_type": "Petrol", "transmission": "Manual", "engine": "2.7L Petrol"},
            {"name": "4x4 2.8 Diesel AT", "fuel_type": "Diesel", "transmission": "Automatic", "engine": "2.8L GD Diesel"},
            {"name": "Legender 4x4 AT", "fuel_type": "Diesel", "transmission": "Automatic", "engine": "2.8L GD Diesel"},
        ],
        "Urban Cruiser Taisor": [
            {"name": "E 1.2 Petrol", "fuel_type": "Petrol", "transmission": "Manual", "engine": "1.2L K-Series"},
            {"name": "V 1.0 Turbo AT", "fuel_type": "Petrol", "transmission": "Automatic", "engine": "1.0L Turbo"},
        ],
    },
    "Honda": {
        "City": [
            {"name": "V 1.5 i-VTEC", "fuel_type": "Petrol", "transmission": "Manual", "engine": "1.5L i-VTEC"},
            {"name": "ZX 1.5 CVT", "fuel_type": "Petrol", "transmission": "CVT", "engine": "1.5L i-VTEC"},
            {"name": "e:HEV Hybrid ZX", "fuel_type": "Hybrid", "transmission": "Automatic", "engine": "1.5L Atkinson Cycle"},
        ],
        "Elevate": [
            {"name": "V 1.5 MT", "fuel_type": "Petrol", "transmission": "Manual", "engine": "1.5L i-VTEC"},
            {"name": "ZX 1.5 CVT", "fuel_type": "Petrol", "transmission": "CVT", "engine": "1.5L i-VTEC"},
        ],
        "Amaze": [
            {"name": "S 1.2 MT", "fuel_type": "Petrol", "transmission": "Manual", "engine": "1.2L i-VTEC"},
            {"name": "VX 1.2 CVT", "fuel_type": "Petrol", "transmission": "CVT", "engine": "1.2L i-VTEC"},
        ],
    },
    "Kia": {
        "Seltos": [
            {"name": "HTE 1.5 Petrol", "fuel_type": "Petrol", "transmission": "Manual", "engine": "1.5L Smartstream"},
            {"name": "HTX 1.5 Diesel AT", "fuel_type": "Diesel", "transmission": "Automatic", "engine": "1.5L CRDi"},
            {"name": "GTX+ 1.5 Turbo DCT", "fuel_type": "Petrol", "transmission": "DCT", "engine": "1.5L Turbo GDi"},
        ],
        "Sonet": [
            {"name": "HTE 1.2 Petrol", "fuel_type": "Petrol", "transmission": "Manual", "engine": "1.2L Smartstream"},
            {"name": "GTX+ 1.5 Diesel AT", "fuel_type": "Diesel", "transmission": "Automatic", "engine": "1.5L CRDi"},
        ],
        "Carens": [
            {"name": "Prestige 1.5 Petrol", "fuel_type": "Petrol", "transmission": "Manual", "engine": "1.5L Smartstream"},
            {"name": "Luxury Plus 1.5 Turbo DCT", "fuel_type": "Petrol", "transmission": "DCT", "engine": "1.5L Turbo GDi"},
        ],
    },
    "Volkswagen": {
        "Taigun": [
            {"name": "Highline 1.0 TSI MT", "fuel_type": "Petrol", "transmission": "Manual", "engine": "1.0L TSI"},
            {"name": "GT Plus 1.5 TSI DSG", "fuel_type": "Petrol", "transmission": "DCT", "engine": "1.5L TSI EVO"},
        ],
        "Virtus": [
            {"name": "Highline 1.0 TSI AT", "fuel_type": "Petrol", "transmission": "Automatic", "engine": "1.0L TSI"},
            {"name": "GT Plus Edge 1.5 TSI DSG", "fuel_type": "Petrol", "transmission": "DCT", "engine": "1.5L TSI EVO"},
        ],
    },
    "Skoda": {
        "Kushaq": [
            {"name": "Ambition 1.0 TSI MT", "fuel_type": "Petrol", "transmission": "Manual", "engine": "1.0L TSI"},
            {"name": "Monte Carlo 1.5 TSI DSG", "fuel_type": "Petrol", "transmission": "DCT", "engine": "1.5L TSI EVO"},
        ],
        "Slavia": [
            {"name": "Ambition 1.0 TSI AT", "fuel_type": "Petrol", "transmission": "Automatic", "engine": "1.0L TSI"},
            {"name": "Style 1.5 TSI DSG", "fuel_type": "Petrol", "transmission": "DCT", "engine": "1.5L TSI EVO"},
        ],
        "Kodiaq": [
            {"name": "L&K 2.0 TSI 4x4", "fuel_type": "Petrol", "transmission": "DCT", "engine": "2.0L TSI"},
        ],
    },
    "MG": {
        "Hector": [
            {"name": "Shine Pro 1.5 Turbo MT", "fuel_type": "Petrol", "transmission": "Manual", "engine": "1.5L Turbo"},
            {"name": "Savvy Pro 2.0 Diesel MT", "fuel_type": "Diesel", "transmission": "Manual", "engine": "2.0L Turbo Diesel"},
        ],
        "Astor": [
            {"name": "Super 1.5 VTi-Tech", "fuel_type": "Petrol", "transmission": "Manual", "engine": "1.5L VTi"},
            {"name": "Savvy 1.3 Turbo AT", "fuel_type": "Petrol", "transmission": "Automatic", "engine": "1.3L Turbo"},
        ],
        "ZS EV": [
            {"name": "Executive 50.3 kWh", "fuel_type": "Electric", "transmission": "Automatic", "engine": "Permanent Magnet Synchronous"},
        ],
    },
    "BMW": {
        "3 Series Gran Limousine": [
            {"name": "320Li M Sport", "fuel_type": "Petrol", "transmission": "Automatic", "engine": "2.0L TwinPower Turbo"},
            {"name": "320d M Sport", "fuel_type": "Diesel", "transmission": "Automatic", "engine": "2.0L Diesel Turbo"},
        ],
        "5 Series": [
            {"name": "530Li M Sport", "fuel_type": "Petrol", "transmission": "Automatic", "engine": "2.0L TwinPower Turbo"},
        ],
        "X5": [
            {"name": "xDrive40i M Sport", "fuel_type": "Petrol", "transmission": "Automatic", "engine": "3.0L Turbo I6"},
            {"name": "xDrive30d xLine", "fuel_type": "Diesel", "transmission": "Automatic", "engine": "3.0L Diesel I6"},
        ],
    },
    "Mercedes-Benz": {
        "C-Class": [
            {"name": "C 200", "fuel_type": "Petrol", "transmission": "Automatic", "engine": "1.5L Turbo Petrol"},
            {"name": "C 220d", "fuel_type": "Diesel", "transmission": "Automatic", "engine": "2.0L Turbo Diesel"},
        ],
        "E-Class": [
            {"name": "E 200 Exclusive", "fuel_type": "Petrol", "transmission": "Automatic", "engine": "2.0L Turbo Petrol"},
            {"name": "E 220d Expression", "fuel_type": "Diesel", "transmission": "Automatic", "engine": "2.0L Turbo Diesel"},
        ],
        "GLE": [
            {"name": "GLE 300d 4MATIC", "fuel_type": "Diesel", "transmission": "Automatic", "engine": "2.0L Turbo Diesel"},
            {"name": "GLE 450 4MATIC", "fuel_type": "Petrol", "transmission": "Automatic", "engine": "3.0L Turbo Petrol"},
        ],
    },
    "Audi": {
        "A4": [
            {"name": "40 TFSI Premium", "fuel_type": "Petrol", "transmission": "Automatic", "engine": "2.0L TFSI"},
            {"name": "40 TFSI Technology", "fuel_type": "Petrol", "transmission": "Automatic", "engine": "2.0L TFSI"},
        ],
        "Q5": [
            {"name": "45 TFSI Technology", "fuel_type": "Petrol", "transmission": "Automatic", "engine": "2.0L TFSI"},
        ],
    },
    "Renault": {
        "Kiger": [
            {"name": "RXT 1.0 Energy MT", "fuel_type": "Petrol", "transmission": "Manual", "engine": "1.0L Energy"},
            {"name": "RXZ 1.0 Turbo CVT", "fuel_type": "Petrol", "transmission": "CVT", "engine": "1.0L Turbo"},
        ],
        "Triber": [
            {"name": "RXT 1.0", "fuel_type": "Petrol", "transmission": "Manual", "engine": "1.0L Energy"},
        ],
    },
    "Nissan": {
        "Magnite": [
            {"name": "XL 1.0 NA MT", "fuel_type": "Petrol", "transmission": "Manual", "engine": "1.0L B4D"},
            {"name": "XV Premium 1.0 Turbo CVT", "fuel_type": "Petrol", "transmission": "CVT", "engine": "1.0L Turbo"},
        ],
    },
    "Jeep": {
        "Compass": [
            {"name": "Sport 2.0 Diesel MT", "fuel_type": "Diesel", "transmission": "Manual", "engine": "2.0L Multijet II"},
            {"name": "Model S 2.0 Diesel AT 4x4", "fuel_type": "Diesel", "transmission": "Automatic", "engine": "2.0L Multijet II"},
        ],
    },
    "Citroen": {
        "C3": [
            {"name": "Feel 1.2 PureTech", "fuel_type": "Petrol", "transmission": "Manual", "engine": "1.2L PureTech"},
            {"name": "Shine 1.2 Turbo", "fuel_type": "Petrol", "transmission": "Manual", "engine": "1.2L Turbo"},
        ],
    },
    "BYD": {
        "Atto 3": [
            {"name": "Extended Range 60.48 kWh", "fuel_type": "Electric", "transmission": "Automatic", "engine": "Permanent Magnet Synchronous"},
        ],
        "Seal": [
            {"name": "Dynamic RWD", "fuel_type": "Electric", "transmission": "Automatic", "engine": "Permanent Magnet"},
            {"name": "Performance AWD", "fuel_type": "Electric", "transmission": "Automatic", "engine": "Dual Motor AWD"},
        ],
    },
    "Volvo": {
        "XC60": [
            {"name": "B5 Ultimate Mild Hybrid", "fuel_type": "Hybrid", "transmission": "Automatic", "engine": "2.0L Turbo Hybrid"},
        ],
    },
    "Jaguar": {
        "F-Pace": [
            {"name": "R-Dynamic S 2.0 Petrol", "fuel_type": "Petrol", "transmission": "Automatic", "engine": "2.0L Ingenium Turbo"},
        ],
    },
    "Land Rover": {
        "Defender": [
            {"name": "110 2.0 SE Petrol", "fuel_type": "Petrol", "transmission": "Automatic", "engine": "2.0L Ingenium"},
            {"name": "110 3.0 Diesel HSE", "fuel_type": "Diesel", "transmission": "Automatic", "engine": "3.0L Ingenium Turbo Diesel"},
        ],
        "Range Rover Velar": [
            {"name": "HSE 2.0 Petrol", "fuel_type": "Petrol", "transmission": "Automatic", "engine": "2.0L Ingenium"},
        ],
    },
}


class Command(BaseCommand):
    help = "Seeds comprehensive Indian vehicle catalog data (CarBrand, CarModel, CarVariant)"

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Starting vehicle catalog seed..."))

        brands_created = 0
        models_created = 0
        variants_created = 0

        for brand_name, models_dict in CATALOG.items():
            brand, b_created = CarBrand.objects.get_or_create(name=brand_name)
            if b_created:
                brands_created += 1

            for model_name, variants_list in models_dict.items():
                # Determine body type hint
                b_type = "SUV" if any(x in model_name.upper() for x in ["XUV", "FORTUNER", "CRETA", "NEXON", "THAR", "SCORPIO", "TAIGUN", "KUSHAQ", "DEFENDER", "XC60", "GLE", "X5", "Q5", "MAGNITE", "KIGER", "SELTOS", "SONET", "VENUE", "FRONX", "BREZZA", "PUNCH", "ATTO"]) else "Sedan" if any(x in model_name.upper() for x in ["CITY", "VERNA", "VIRTUS", "SLAVIA", "A4", "C-CLASS", "E-CLASS", "3 SERIES", "5 SERIES", "SEAL", "AMAZE"]) else "Hatchback"

                car_model, m_created = CarModel.objects.get_or_create(
                    brand=brand,
                    name=model_name,
                    defaults={"body_type": b_type}
                )
                if m_created:
                    models_created += 1

                for v_info in variants_list:
                    variant, v_created = CarVariant.objects.get_or_create(
                        model=car_model,
                        name=v_info["name"],
                        defaults={
                            "fuel_type": v_info.get("fuel_type", "Petrol"),
                            "transmission": v_info.get("transmission", "Manual"),
                            "engine": v_info.get("engine", ""),
                        }
                    )
                    if v_created:
                        variants_created += 1

        self.stdout.write(self.style.SUCCESS(
            f"Successfully seeded catalog!\n"
            f"Brands created/ensured: {CarBrand.objects.count()} (new: {brands_created})\n"
            f"Models created/ensured: {CarModel.objects.count()} (new: {models_created})\n"
            f"Variants created/ensured: {CarVariant.objects.count()} (new: {variants_created})"
        ))
