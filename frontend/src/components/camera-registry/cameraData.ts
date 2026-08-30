export interface RegistryCamera {
  id: number;
  code: string;
  name: string;
  city: string;
  source_type: "ONVIF" | "RTSP" | "VENDOR_API";
  camera_type: string;
  status: "online" | "offline";
  amc_status: "active" | "expired";
  department: string;
}

export interface CityCameraGroup {
  city: string;
  cityNameUppercase: string;
  totalCount: number;
  cameras: RegistryCamera[];
}

export const INITIAL_CAMERA_GROUPS: CityCameraGroup[] = [
  {
    city: "Ahmedabad",
    cityNameUppercase: "AHMEDABAD",
    totalCount: 214,
    cameras: [
      {
        id: 1,
        code: "AMD-AP-01",
        name: "Airport Approach Road",
        city: "Ahmedabad",
        source_type: "ONVIF",
        camera_type: "ip",
        status: "online",
        amc_status: "active",
        department: "Ahmedabad City Police",
      },
      {
        id: 2,
        code: "AMD-AS-01",
        name: "Ashram Road Paldi",
        city: "Ahmedabad",
        source_type: "RTSP",
        camera_type: "ip",
        status: "online",
        amc_status: "active",
        department: "Ahmedabad City Police",
      },
      {
        id: 3,
        code: "AMD-BA-01",
        name: "Bapunagar Crossroads",
        city: "Ahmedabad",
        source_type: "RTSP",
        camera_type: "ip",
        status: "online",
        amc_status: "active",
        department: "Ahmedabad City Police",
      },
      {
        id: 4,
        code: "AMD-NV-01",
        name: "Navrangpura University",
        city: "Ahmedabad",
        source_type: "VENDOR_API",
        camera_type: "ip",
        status: "online",
        amc_status: "active",
        department: "Ahmedabad City Police",
      },
      {
        id: 5,
        code: "AMD-TH-01",
        name: "Thaltej Shilaj Road",
        city: "Ahmedabad",
        source_type: "ONVIF",
        camera_type: "ip",
        status: "online",
        amc_status: "active",
        department: "Ahmedabad City Police",
      },
    ],
  },
  {
    city: "Vadodara",
    cityNameUppercase: "VADODARA",
    totalCount: 78,
    cameras: [
      {
        id: 6,
        code: "VAD-MK-01",
        name: "Manjalpur Circle",
        city: "Vadodara",
        source_type: "ONVIF",
        camera_type: "ip",
        status: "online",
        amc_status: "active",
        department: "Vadodara City Police",
      },
      {
        id: 7,
        code: "VAD-RC-01",
        name: "Race Course Road",
        city: "Vadodara",
        source_type: "RTSP",
        camera_type: "ip",
        status: "offline",
        amc_status: "expired",
        department: "Vadodara City Police",
      },
      {
        id: 8,
        code: "VAD-SN-01",
        name: "Sayajigunj Circle",
        city: "Vadodara",
        source_type: "VENDOR_API",
        camera_type: "ip",
        status: "online",
        amc_status: "active",
        department: "Vadodara City Police",
      },
    ],
  },
  {
    city: "Surat",
    cityNameUppercase: "SURAT",
    totalCount: 64,
    cameras: [
      {
        id: 9,
        code: "SUR-CT-01",
        name: "City Light Crossroad",
        city: "Surat",
        source_type: "RTSP",
        camera_type: "ip",
        status: "online",
        amc_status: "active",
        department: "Surat City Police",
      },
      {
        id: 10,
        code: "SUR-PN-01",
        name: "Piplod Naka",
        city: "Surat",
        source_type: "ONVIF",
        camera_type: "ip",
        status: "offline",
        amc_status: "expired",
        department: "Surat City Police",
      },
      {
        id: 11,
        code: "SUR-DM-01",
        name: "Dumas Road",
        city: "Surat",
        source_type: "VENDOR_API",
        camera_type: "ip",
        status: "online",
        amc_status: "active",
        department: "Surat City Police",
      },
    ],
  },
  {
    city: "Rajkot",
    cityNameUppercase: "RAJKOT",
    totalCount: 34,
    cameras: [
      {
        id: 12,
        code: "RJK-KL-01",
        name: "Kalawad Road Crossway",
        city: "Rajkot",
        source_type: "ONVIF",
        camera_type: "ip",
        status: "online",
        amc_status: "active",
        department: "Rajkot City Police",
      },
      {
        id: 13,
        code: "RJK-YR-01",
        name: "Yagnik Road Central",
        city: "Rajkot",
        source_type: "RTSP",
        camera_type: "ip",
        status: "online",
        amc_status: "active",
        department: "Rajkot City Police",
      },
      {
        id: 14,
        code: "RJK-TR-01",
        name: "Trikon Baug Junction",
        city: "Rajkot",
        source_type: "VENDOR_API",
        camera_type: "ip",
        status: "offline",
        amc_status: "expired",
        department: "Rajkot City Police",
      },
    ],
  },
  {
    city: "Gandhinagar",
    cityNameUppercase: "GANDHINAGAR",
    totalCount: 22,
    cameras: [
      {
        id: 15,
        code: "GNR-CH-01",
        name: "CH-0 Highway Crossing",
        city: "Gandhinagar",
        source_type: "ONVIF",
        camera_type: "ip",
        status: "online",
        amc_status: "active",
        department: "Gandhinagar Police",
      },
      {
        id: 16,
        code: "GNR-GH-01",
        name: "GH Road Secretariat",
        city: "Gandhinagar",
        source_type: "RTSP",
        camera_type: "ip",
        status: "online",
        amc_status: "active",
        department: "Gandhinagar Police",
      },
      {
        id: 17,
        code: "GNR-IN-01",
        name: "Infocity IT Hub Circle",
        city: "Gandhinagar",
        source_type: "VENDOR_API",
        camera_type: "ip",
        status: "online",
        amc_status: "active",
        department: "Gandhinagar Police",
      },
    ],
  },
];
