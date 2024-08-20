import React from 'react';
import { Bar } from 'react-chartjs-2';
import { Chart as ChartJS, CategoryScale, LinearScale, BarElement, Title, Tooltip, Legend } from 'chart.js';

// Register the necessary components for Chart.js
ChartJS.register(
  CategoryScale,
  LinearScale,
  BarElement,
  Title,
  Tooltip,
  Legend
);

const AverageValueComparisonChart = ({ cattleList, startDate, endDate }) => {
  const averageValueComparison = (cattleList, startDate, endDate) => {
    const values = {};

    cattleList.forEach(cattle => {
      const filteredValues = cattle.values.filter(v => new Date(v.date) >= new Date(startDate) && new Date(v.date) <= new Date(endDate));
      const average = filteredValues.reduce((acc, v) => acc + v.value * cattle.weight / 100, 0) / filteredValues.length;
      values[cattle.type] = average;
    });

    return {
      labels: Object.keys(values),
      datasets: [{
        label: 'Average Value (USD)',
        data: Object.values(values),
        backgroundColor: 'rgba(75, 192, 192, 0.5)',
      }],
    };
  };

  const avgComparisonData = averageValueComparison(cattleList, startDate, endDate);

  const options = {
    responsive: true,
    plugins: {
      legend: {
        position: 'top',
      },
      tooltip: {
        callbacks: {
          label: function(context) {
            const value = context.raw.toFixed(2);
            return `$${value}`;
          }
        }
      },
    },
    scales: {
      x: {
        title: {
          display: true,
          text: 'Cattle Type',
        },
      },
      y: {
        title: {
          display: true,
          text: 'Average Value (USD)',
        },
        ticks: {
          callback: (value) => `$${value.toFixed(2)}`,
        },
      },
    },
  };

  return (
    <div>
      <h2>Average Value Comparison</h2>
      <Bar data={avgComparisonData} options={options} />
    </div>
  );
};

export default AverageValueComparisonChart;
