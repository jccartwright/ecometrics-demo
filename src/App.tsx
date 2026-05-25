import { useState, useEffect, useRef} from 'react'
import { useLoadJSON } from './hooks/useLoadJson'
import * as Plot from "@observablehq/plot"
// import * as d3 from "d3"
import filePrefixes from './input_files.json'

import './App.css'
// import NavButtonPanel from './components/nav-button-panel'


interface Well {
    id: string
    x: number
    min_z: number
    max_z: number
    surface: number
    sensor: number
  }

interface Elevation {
    distance_along_profile: number
    elevation: number
}

interface WaterLevelEntry {
  id?: string
  bs?: boolean
  x: number
  z: number
}

interface WaterLevel {
  label: string
  beavers?: number
  mimicry?: number
  measured: WaterLevelEntry[]
  interpolated: WaterLevelEntry[]
  surface_water_area?: number
  unsaturated_area?: number
}


function App() {
  const containerRef = useRef<HTMLDivElement | null>(null)
  // useRef instead of simple variable to avoid a dependency in the useEffect controlling the animation
  const maxIndexRef = useRef<number>(0)
  const [filePrefix, setFilePrefix] = useState(filePrefixes[0])
  const [waterlevelIndex, setWaterlevelIndex] = useState(0)
  const [running, setRunning] = useState(false)
  // console.log('rendering App with waterlevelIndex', waterlevelIndex, 'and filePrefix', filePrefix)

  function timestepChangeHandler(event: React.ChangeEvent<HTMLInputElement>) {
    setWaterlevelIndex(event.target.valueAsNumber);  
  }

  // expects file in public folder
  const { data:wellsData, loading:wellsLoading, error:wellsError } = useLoadJSON<Well[]>(`./data/${filePrefix}_wells.json`)
  const { data:elevationsData, loading:elevationsLoading, error:elevationsError } = useLoadJSON<Elevation[]>(`./data/${filePrefix}_elevations.json`)
  const { data:waterlevelsData, loading:waterlevelsLoading, error:waterlevelsError } = useLoadJSON<WaterLevel[]>(`./data/${filePrefix}_waterlevels.json`)

  useEffect(() => {
    if (!running) return

    const interval = setInterval(() => {
      setWaterlevelIndex(prev => {
        if (prev >= maxIndexRef.current) {
          setRunning(false)
          return prev
        }
        return prev + 1
      })
    }, 100)

    return () => clearInterval(interval)
  }, [running]);

  useEffect(() => {
    if (!waterlevelsData) {
      console.log('waterlevels data not yet loaded')
      return
    }
    maxIndexRef.current = waterlevelsData.length - 1

    if (!wellsData) {
      // console.log('wells data not yet loaded')
      return
    }
    if (!elevationsData) {
      // console.log('elevations data not yet loaded')
      return
    }

    function getDotColor(entry: WaterLevelEntry): string {
      if (entry.bs) {
        return "red"
      }
      return "blue"
    }

    function formatPopup(entry: WaterLevelEntry): string {
      // should not happen since we check for wellsData before, but typescript doesn't know that
      if (!wellsData) {
        // return `water level: ${entry.z} m`
        console.log('Error: wellsData not loaded when formatting popup')
        return ""
      }

      // get the well associated with this water level entry
      const well = wellsData.find(well => well.x === entry.x)
      // possible to have a water level measurement that is not associated with a well
      if (!well) {
        return `water level: ${entry.z} ft`
      }
      const strings = []
      strings.push(`well ${well.id}`)
      strings.push(`sensor ${(well.surface - well.sensor).toFixed(1)} ft below surface`)
      // although the popup should not be accessible with missing data since 
      // there is no dot to hover over, formatPopup() is still called
      const waterLevelString = entry.z ? `${(entry.z).toLocaleString('en',{maximumFractionDigits:1})} ft` : "no reading"
      strings.push (entry.bs ? 'Below Sensor': `water level: ${waterLevelString}`)
      return strings.join('\n')
    }
    
    // get data for this timestep
    const waterlevelData = waterlevelsData[waterlevelIndex]
    console.log({waterlevelData})
    
    const plotCaption = 
      `${wellsData.length} wells, ${elevationsData.length} survey stations, and ${waterlevelsData.length.toLocaleString()} total water level measurements.
      Data from ${waterlevelsData[0]?.label.split(' ')[0]} to ${waterlevelsData[waterlevelsData.length -1]?.label.split(' ')[0]}.` 

    // data for the beaver dam intensity plot bar chart
    const plot1Data = [
      {name: "Beavers", value: waterlevelData?.beavers ? waterlevelData?.beavers : 0},
      {name: "Mimicry", value: waterlevelData?.mimicry ? waterlevelData.mimicry : 0}
    ]
    
    function getBeaverLabel(value: number): string {
      const labels = ['','low intensity', 'moderate intensity', 'high intensity']
      return labels[value]
    }
    
    const plot1 = Plot.frame().plot({
      width: 400,
      y: {label: null},
      x: {axis: null},
      marginLeft: 90,
      
      marks:[
        Plot.ruleX([3], {stroke:[]}),
        Plot.barX(plot1Data, { x: "value", y: "name"}),
        Plot.text(plot1Data, {
          text: d => getBeaverLabel(d.value),
            y: "name",
            x: "value",
            textAnchor: "end",
            dx: -3,
            fill: "white"
        })
      ]
    })

    // console.log('starting Plot generation with waterlevel index', waterlevelIndex, waterlevelData)
    const plot = Plot.plot({
      caption: plotCaption,
      width: 1500,
      marginLeft: 60,
      style: {fontSize: "14px"},
      marginBottom: 50,
      grid: true,
      color: {
        legend: true,
      },
      marks: [
        Plot.axisY({label: "Elevation (ft)"}),
        Plot.axisX({label: "Distance along profile (ft)", labelOffset: 40}),
        Plot.line(
          elevationsData, {
            x: "x", 
            y: "z",
            title: (d) => `elev: ${d.z} ft`, 
            stroke: "black", 
            tip: false
          }),
        Plot.line(waterlevelData?.interpolated, {x: "x", y: "z", stroke: "red", strokeDasharray: "4 4"}),
        Plot.line(waterlevelData?.measured, {x: "x", y: "z", stroke: "mediumblue", strokeWidth: 5}),
        Plot.dot(waterlevelData?.measured, { 
          x: "x", 
          y: "z", 
          r: 6, 
          fill: (d) => getDotColor(d),
          title: (d) => formatPopup(d),
          stroke: "blue",
          tip: true
        }),
        Plot.rect(wellsData, {
          x1: ((d:Well) => d.x - 0.5),
          x2: (d:Well) => d.x + 0.5,
          // y1: (d:Well) => d.min_z,
          y1: (d:Well) => d.sensor,
          y2: (d:Well) => d.max_z,
          stroke: "black",
          fillOpacity: 0.1,
          fill: "blue",
          // tip: true,
          // title: (d:Well) => `Well ${d.id}\nSensor: ${d.sensor} m\nMin: ${d.min_z} m\nMax: ${d.max_z} m`
        })
      ]
    })
    
    containerRef?.current?.append(plot1,plot);

    return () => {
      plot.remove()
      plot1.remove()
    }
  }, [wellsData, elevationsData, waterlevelsData, waterlevelIndex, filePrefix])

  if (wellsLoading || elevationsLoading || waterlevelsLoading) return <div>Loading data...</div>
  if (wellsError || elevationsError || waterlevelsError) return <div>Error loading data</div>
  if (!(wellsData && elevationsData && waterlevelsData )) return <div>no data</div> // no data in files - should not happen
  
  function formatAreaStats() {
    if (!(waterlevelsData && waterlevelsData[waterlevelIndex])) {
      return <p>water level data not available</p>
    }
    const waterlevelData = waterlevelsData[waterlevelIndex]
    if (waterlevelData.surface_water_area === undefined || waterlevelData.unsaturated_area === undefined) {
      return (
        <>
        <p>surfaceWaterArea: N/A</p>
        <p>unsaturatedArea: N/A</p>
        </>
      )
    }
    
    const surfaceWaterArea = waterlevelData.surface_water_area
    const unsaturatedArea = waterlevelData.unsaturated_area
    const totalArea = surfaceWaterArea + unsaturatedArea

    const  surfacePct = surfaceWaterArea === 0? 0 : (surfaceWaterArea / totalArea * 100)?.toFixed(2)
    const unsaturatedPct = unsaturatedArea === 0? 0 : (unsaturatedArea / totalArea * 100)?.toFixed(2)    
    
    return (
      <>
        <p>surface water area: {surfaceWaterArea} ft² ({surfacePct}%)</p>
        <p>unsaturated area: {unsaturatedArea} ft² ({unsaturatedPct}%)</p>
      </>
    )
  }

  return (
    <>
      <h1 style={{fontSize: "24px", fontWeight: "bold", marginBottom: "10px"}}>{filePrefix.replaceAll("_", " ")} Groundwater Level</h1>
      <div ref={containerRef} />
      <div className="card" style={{position: "relative", backgroundColor: "lightgray", padding: "20px", margin: "20px"}}>
        <div style={{position: "absolute", top: "5px", left: "5px", fontWeight: "bold", fontSize: "16px", border: "1px solid #ccc", padding: "10px"}}>
          {formatAreaStats()}
        </div>
        <p style={{marginBottom:"5px", fontWeight: "bold"}}>Datetime: {waterlevelsData[waterlevelIndex]?.label}</p>
        <button style={{backgroundColor: "darkgray"}} onClick={() => setRunning(r => !r)}>
          {running ? "Stop Animation" : "Start Animation"}
        </button>
        <button style={{backgroundColor: "darkgray"}} onClick={() => { setRunning(false); setWaterlevelIndex(0); }}>
          Reset
        </button>
        <select style={{backgroundColor:"darkgray",  padding: "10px", marginLeft: "30px"}} value={filePrefix} onChange={(e) => { setFilePrefix(e.target.value); setWaterlevelIndex(0); setRunning(false); }}>
          {filePrefixes?.map((file) => (
            <option key={file} value={file}>
              {file}
            </option>
          ))}
        </select>
        <div style={{marginTop: "20px"}}>
          <div>
            <label htmlFor={"time-range"}>Select a time step (0 to {waterlevelsData.length - 1}):</label>
          </div>
          <input style={{width: "500px"}} onChange={timestepChangeHandler} type="range" id="time-range" name="time-range" min="0" max={waterlevelsData.length-1} value={waterlevelIndex}/>
        </div>
      </div>
      <div id="footer" style={{backgroundColor:"white", alignContent: "center", padding: "10px", margin: "20px", fontSize: "12px"}}>
        ©2026 EcoMetrics Colorado | <a href="https://www.ecometricscolorado.org/">www.ecometricscolorado.org</a>
      </div>
    </>
  )
}
export default App