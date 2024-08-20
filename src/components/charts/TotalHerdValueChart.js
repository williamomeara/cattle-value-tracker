import React from 'react';
import { Line } from 'react-chartjs-2';
import { Chart as ChartJS, CategoryScale, LinearScale, LineElement, PointElement, Title, Tooltip, Legend, TimeScale } from 'chart.js';
import 'chartjs-adapter-date-fns'; // Import date-fns for date handling

// Register the necessary components for Chart.js
ChartJS.register(
  CategoryScale,
  LinearScale,
  LineElement,
  PointElement,
  Title,
  Tooltip,
  Legend,
  TimeScale // Register the TimeScale component
);

const TotalHerdValueChart = ({ cattleList }) => {
  const aggregateHerdValues = (cattleList) => {
    const valueMap = {};

    cattleList.forEach(cattle => {
      cattle.values.forEach(v => {
        if (!valueMap[v.date]) {
          valueMap[v.date] = 0;
        }
        valueMap[v.date] += v.value * cattle.weight / 100; // Convert cents to dollars
      });
    });

    return Object.keys(valueMap).map(date => ({
      x: date,
      y: valueMap[date],
    }));
  };

  const herdData = {
    labels: [],
    datasets: [{
      label: 'Total Herd Value',
      data: aggregateHerdValues(cattleList),
      borderColor: 'rgba(75, 192, 192, 1)',
      backgroundColor: 'rgba(75, 192, 192, 0.5)',
      fill: false,
    }],
  };

  const options = {
    responsive: true,
    plugins: {
      legend: {
        position: 'top',
      },
      tooltip: {
        mode: 'index',
        intersect: false,
        callbacks: {
          label: function(context) {
            const value = context.raw.y.toFixed(2); // Format value to 2 decimal places
            return `$${value}`; // Show value in dollars
          }
        }
      },
    },
    scales: {
      x: {
        type: 'time',
        time: {
          unit: 'month',
        },
        title: {
          display: true,
          text: 'Date',
        },
      },
      y: {
        title: {
          display: true,
          text: 'Value (USD)',
        },
        ticks: {
          callback: (value) => `$${value.toFixed(2)}`, // Format y-axis labels
        },
      },
    },
  };

  return (
    <div>
      <h2>Total Herd Value Over Time</h2>
      <Line data={herdData} options={options} />
    </div>
  );
};

export default TotalHerdValueChart;
