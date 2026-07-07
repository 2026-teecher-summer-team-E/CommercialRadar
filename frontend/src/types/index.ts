export interface CommercialDistrict {
  id: number;
  district_name: string;
  type_name: string | null;
  gu_name: string | null;
  dong_name: string | null;
  avg_population: number | null;
  area_name: string | null;
}

export interface BusinessCategory {
  id: number;
  commercial_district_id: number;
  category_name: string | null;
  year_quarter: string;
  closure_rate: number | null;
  survival_rate: number | null;
  open_rate: number | null;
  total_business: number | null;
  total_sales: number | null;
}

export type PredictionType = "survival" | "population" | "sales";
