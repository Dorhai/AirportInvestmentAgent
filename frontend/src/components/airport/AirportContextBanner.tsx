import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { AlertTriangle, Cloud, Building2 } from "lucide-react";
import type { components } from "@/types/api.generated";

type AirportContext = components["schemas"]["AirportContext"];
type WeatherContext = components["schemas"]["WeatherContext"];

function isUsableWeather(weather: WeatherContext | null | undefined): boolean {
  if (!weather) return false;
  const cat = weather.flight_category?.trim();
  if (!cat || cat.toLowerCase() === "unknown") return false;
  return true;
}

interface AirportContextBannerProps {
  context?: AirportContext | null;
}

export function AirportContextBanner({ context }: AirportContextBannerProps) {
  if (!context) return null;

  const hasNas = !!context.nas_delay_program;
  const hasWeather = isUsableWeather(context.weather);
  const hasFacility = !!context.facility;

  if (!hasNas && !hasWeather && !hasFacility) return null;

  return (
    <div className="flex flex-col gap-2 mb-4">
      {hasNas && (
        <Alert variant="destructive" className="bg-destructive/10">
          <AlertTriangle className="h-4 w-4" />
          <AlertTitle>Active FAA NAS Delay Program</AlertTitle>
          <AlertDescription>
            {context.nas_delay_program?.program} due to {context.nas_delay_program?.reason} 
            (Avg delay: {context.nas_delay_program?.avg_delay})
          </AlertDescription>
        </Alert>
      )}

      {(hasWeather || hasFacility) && (
        <div className="flex flex-wrap gap-4 text-xs text-muted-foreground bg-muted/50 p-2 rounded-md">
          {hasWeather && (
            <div className="flex items-center gap-1">
              <Cloud className="h-3 w-3" />
              <span>
                {context.weather?.flight_category} • {context.weather?.wind} • Vis:{" "}
                {context.weather?.visibility}
              </span>
            </div>
          )}
          {hasFacility && (
            <div className="flex items-center gap-1">
              <Building2 className="h-3 w-3" />
              <span>
                {context.facility?.acreage ? `${context.facility.acreage.toLocaleString()} acres` : "Unknown size"} • 
                Class {context.facility?.part139_class || "?"} • 
                Tower: {context.facility?.tower_type || "None"}
              </span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
