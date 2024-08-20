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

const IndividualCattleValueChart = ({ cattleList }) => {
  const individualData = {
    labels: [],
    datasets: cattleList.map((cattle, index) => ({
      label: `${cattle.type.replace('_', ' ').toUpperCase()} - Weight: ${cattle.weight} kg`,
      data: cattle.values.map(v => ({ x: v.date, y: v.value * cattle.weight / 100 })), // Convert cents to dollars
      borderColor: `rgba(${index * 50 % 255}, ${index * 100 % 255}, ${index * 150 % 255}, 1)`,
      backgroundColor: `rgba(${index * 50 % 255}, ${index * 100 % 255}, ${index * 150 % 255}, 0.5)`,
      fill: false,
    })),
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
      <h2>Cattle Value Over Time</h2>
      <Line data={individualData} options={options} />
    </div>
  );
};

export default IndividualCattleValueChart;
