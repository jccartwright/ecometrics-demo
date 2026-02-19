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
  id: string
  x: number
  z: number
}

interface WaterLevel {
  label: string
  values: WaterLevelEntry[]
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
    }, 1000)

    return () => clearInterval(interval)
  }, [running]);

  useEffect(() => {
    if (!waterlevelsData) {
      // console.log('waterlevels data not yet loaded')
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
    const waterlevelData = waterlevelsData[waterlevelIndex]
    // console.log('starting Plot generation with waterlevel index', waterlevelIndex, waterlevelData)
    const plot = Plot.plot({
      width: 1500,
      marginLeft: 50,
      grid: true,
      color: {
        legend: true,
      },
      marks: [
        Plot.line(elevationsData, {x: "x", y: "z", stroke: "red"}),
        Plot.line(waterlevelData?.values, {x: "x", y: "z", stroke: "green"}),
        Plot.dot(waterlevelData?.values, { x: "x", y: "z", r: 6, fill: "green", stroke: "green"}),
        Plot.rect(wellsData, {
          x1: ((d:Well) => d.x - 0.5),
          x2: (d:Well) => d.x + 0.5,
          // y1: (d:Well) => d.min_z,
          y1: (d:Well) => d.sensor,
          y2: (d:Well) => d.max_z,
          stroke: "black",
          fillOpacity: 0.1,
          fill: "blue"
        })
      ]
    })
    
    // const plot = Plot.plot({
    //   y: {grid: true},
    //   color: {scheme: "burd"},
    //   marks: [
    //     Plot.ruleY([0]),
    //     Plot.dot(waterlevelData?.values, 
    //       {x: "x", y: "z", stroke: "green", fill: "green", r: 4, title: d => `Well ${d.id}\nWaterlevel: ${d.z} m`})
    //     ]
    // });
    containerRef?.current?.append(plot);

    return () => plot.remove();
  }, [wellsData, elevationsData, waterlevelsData, waterlevelIndex]);

  if (wellsLoading || elevationsLoading || waterlevelsLoading) return <div>Loading data...</div>
  if (wellsError || elevationsError || waterlevelsError) return <div>Error loading data</div>
  if (!(wellsData && elevationsData && waterlevelsData )) return <div>no data</div> // no data in files - should not happen
  
  
  return (
    <>
      <div ref={containerRef} />
      <div>
        <p>
          {wellsData.length} wells, {elevationsData.length} survey stations, and {waterlevelsData.length.toLocaleString()} water level measurements from {waterlevelsData[0]?.label} to {waterlevelsData[waterlevelsData.length -1]?.label}
        </p>
      </div>
      <div className="card">
        <p>Active Datetime: {waterlevelsData[waterlevelIndex]?.label}</p>
        <button onClick={() => setRunning(r => !r)}>
          {running ? "Stop Animation" : "Start Animation"}
        </button>
        <button onClick={() => { setRunning(false); setWaterlevelIndex(0); }}>
          Reset
        </button>
        <select style={{marginLeft: "20px"}} value={filePrefix} onChange={(e) => setFilePrefix(e.target.value)}>
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
    </>
  )
}
export default App